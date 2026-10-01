#!/usr/bin/env bash
#
# updi-programmer-flash.sh — write the Bread Modular UPDIProgrammer firmware
# (jtag2updi on an ATtiny1616) to the programmer board's own chip.
#
# Shared tool: projects symlink it, e.g.
#   opt/UPDIProgrammer/firmware/flash.sh -> ../../attiny1616-tools/updi-programmer-flash.sh
# and the firmware image (jtag2updi_t1616.hex) stays next to that symlink.
#
# A board cannot program itself: connect a *second* UPDI-capable programmer
# (another UPDIProgrammer board, or any jtag2updi / serialupdi adapter) over
# USB-serial and point this script at that port. The fuse + flash sequence is
# the one documented in opt/UPDIProgrammer/firmware/readme.txt.
#
# Usage:
#   ./flash.sh                    list the serial ports and pick one
#   ./flash.sh /dev/ttyUSB0       explicit port (the suggested default)
#   ./flash.sh --port /dev/ttyUSB1
#   ./flash.sh --list             only show the candidate serial ports
#   PORT=/dev/ttyUSB1 ./flash.sh  port via the environment
#   PROGRAMMER=serialupdi ./flash.sh   plain USB-serial + 4.7 kOhm resistor
#   ./flash.sh --no-fuses         keep the chip's current fuse bytes
#   ./flash.sh --dry-run          read the chip but write nothing
#
# Environment overrides: PORT, PORT_DEFAULT (pre-selected candidate, default
# /dev/ttyUSB0), PROGRAMMER (jtag2updi), PART (t1616), BAUD (unset = the
# programmer's own default, 115200 for jtag2updi), HEX_FILE, AVRDUDE,
# AVRDUDE_CONF, SKIP_FUSES=1.
#
set -euo pipefail

# Directory the user called us from (the project dir holding the .hex, even when
# this script is reached through a symlink).
CALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Real location of this script (follow the symlink) — opt/attiny1616-tools/.
SELF="${BASH_SOURCE[0]}"
while [[ -L "$SELF" ]]; do
  DIR="$(cd -P "$(dirname "$SELF")" && pwd)"
  TARGET="$(readlink "$SELF")"
  [[ "$TARGET" != /* ]] && TARGET="$DIR/$TARGET"
  SELF="$TARGET"
done
TOOLS_DIR="$(cd -P "$(dirname "$SELF")" && pwd)"

HEX_BASENAME="jtag2updi_t1616.hex"
# Where the firmware image may live, in order of preference.
HEX_CANDIDATES=(
  "$CALL_DIR/$HEX_BASENAME"
  "$TOOLS_DIR/../UPDIProgrammer/firmware/$HEX_BASENAME"
)

PORT_DEFAULT="${PORT_DEFAULT:-/dev/ttyUSB0}"
PROGRAMMER="${PROGRAMMER:-jtag2updi}"
PART="${PART:-t1616}"
BAUD="${BAUD:-}"
AVRDUDE="${AVRDUDE:-avrdude}"
AVRDUDE_CONF="${AVRDUDE_CONF:-}"
SKIP_FUSES="${SKIP_FUSES:-0}"
HEX_FILE="${HEX_FILE:-}"

# Fuse bytes exactly as in readme.txt (fuse0/1/2/4/5/6/7/8). avrdude runs the
# chip erase (-e) before the -U operations, so writing the fuses here is what
# makes them stick.
FUSE_OPS=(
  "fuse0:w:0x00:m"
  "fuse1:w:0b00000000:m"
  "fuse2:w:0x02:m"
  "fuse4:w:0x00:m"
  "fuse5:w:0xC7:m"
  "fuse6:w:0x03:m"
  "fuse7:w:0x00:m"
  "fuse8:w:0x00:m"
)

PORT="${PORT:-}"
DRY_RUN=0
LIST_ONLY=0

usage() {
  cat <<'EOF'
flash.sh — write the UPDIProgrammer firmware (jtag2updi, ATtiny1616) over USB-serial.

Usage:
  ./flash.sh                    list the serial ports and pick one
  ./flash.sh /dev/ttyUSB0       explicit port (the suggested default)
  ./flash.sh --port PORT        explicit port
  ./flash.sh --list             show the candidate serial ports and exit
  ./flash.sh --no-fuses         skip the fuse bytes, flash the firmware only
  ./flash.sh --dry-run          read the chip but write nothing (avrdude -n)
  ./flash.sh -h | --help        this help

Options:
  --programmer NAME             avrdude programmer (default: jtag2updi)
  --part NAME                   avrdude part (default: t1616)
  --baud N                      serial baud rate (default: avrdude's own)
  --conf FILE                   avrdude config file (avrdude -C)
  -v, --verbose                 verbose output from this script
EOF
}

log() { printf '==> %s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -p|--port) PORT="${2:-}"; [[ -n "$PORT" ]] || die "--port needs a value"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --programmer) PROGRAMMER="${2:-}"; [[ -n "$PROGRAMMER" ]] || die "--programmer needs a value"; shift 2 ;;
    --programmer=*) PROGRAMMER="${1#*=}"; shift ;;
    --part) PART="${2:-}"; [[ -n "$PART" ]] || die "--part needs a value"; shift 2 ;;
    --part=*) PART="${1#*=}"; shift ;;
    --baud) BAUD="${2:-}"; [[ -n "$BAUD" ]] || die "--baud needs a value"; shift 2 ;;
    --baud=*) BAUD="${1#*=}"; shift ;;
    --conf) AVRDUDE_CONF="${2:-}"; [[ -n "$AVRDUDE_CONF" ]] || die "--conf needs a value"; shift 2 ;;
    --conf=*) AVRDUDE_CONF="${1#*=}"; shift ;;
    --no-fuses|--flash-only) SKIP_FUSES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --list) LIST_ONLY=1; shift ;;
    -v|--verbose) set -x; shift ;;
    --) shift; break ;;
    -*) die "unknown option: $1 (try --help)" ;;
    *) PORT="$1"; shift ;;
  esac
done
[[ $# -eq 0 ]] || die "unexpected arguments: $*"

# ---------------------------------------------------------------------------
# Serial port detection / selection
# ---------------------------------------------------------------------------
PORTS=()
collect_ports() {
  local pattern p
  PORTS=()
  for pattern in /dev/ttyUSB* /dev/ttyACM* \
                 /dev/cu.usbserial* /dev/cu.usbmodem* \
                 /dev/tty.usbserial* /dev/tty.usbmodem*; do
    for p in $pattern; do
      [[ -c "$p" || -e "$p" ]] || continue
      PORTS+=("$p")
    done
  done
}

print_ports() {
  local i
  [[ ${#PORTS[@]} -gt 0 ]] || return 0
  for i in "${!PORTS[@]}"; do
    printf '  %d) %s\n' "$((i + 1))" "${PORTS[$i]}"
  done
}

# Interactive picker. The preferred port (PORT_DEFAULT when it is present) is
# offered as the default, so pressing Enter selects it.
choose_port() {
  local i default_idx=-1 sel
  [[ ${#PORTS[@]} -gt 0 ]] || return 1
  for i in "${!PORTS[@]}"; do
    if [[ -n "$PORT_DEFAULT" && "${PORTS[$i]}" == "$PORT_DEFAULT" ]]; then
      default_idx="$i"
      break
    fi
  done
  [[ "$default_idx" -ge 0 ]] || default_idx=0

  if [[ ! -t 0 ]]; then
    echo "No serial port selected and stdin is not a terminal." >&2
    echo "Candidate ports:" >&2
    print_ports >&2
    die "pass the port explicitly, e.g. ./flash.sh ${PORTS[$default_idx]}"
  fi

  log "Select the serial port of the UPDI adapter:"
  for i in "${!PORTS[@]}"; do
    if [[ "$i" -eq "$default_idx" ]]; then
      printf '  %d) %s  (default)\n' "$((i + 1))" "${PORTS[$i]}"
    else
      printf '  %d) %s\n' "$((i + 1))" "${PORTS[$i]}"
    fi
  done

  while true; do
    printf 'Enter number (1-%d) [%d]: ' "${#PORTS[@]}" "$((default_idx + 1))"
    read -r sel || sel=""
    [[ -n "$sel" ]] || sel="$((default_idx + 1))"
    if [[ "$sel" =~ ^[0-9]+$ ]] && ((sel >= 1 && sel <= ${#PORTS[@]})); then
      PORT="${PORTS[$((sel - 1))]}"
      return 0
    fi
    echo "Invalid selection. Try again." >&2
  done
}

collect_ports

if [[ "$LIST_ONLY" == 1 ]]; then
  if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "No serial ports found."
  else
    echo "Candidate serial ports:"
    print_ports
  fi
  exit 0
fi

if [[ -z "$PORT" ]]; then
  if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "No serial ports found. Plug in the USB-serial UPDI adapter and retry, or pass a port:" >&2
    echo "  ./flash.sh /dev/ttyUSB0" >&2
    exit 1
  elif [[ ${#PORTS[@]} -eq 1 ]]; then
    PORT="${PORTS[0]}"
    log "Only one serial port found: $PORT"
  else
    choose_port
  fi
elif [[ ! -e "$PORT" ]]; then
  echo "Serial port not found: $PORT" >&2
  if [[ ${#PORTS[@]} -gt 0 ]]; then
    echo "Candidate ports:" >&2
    print_ports >&2
  else
    echo "No serial ports found at all." >&2
  fi
  exit 1
fi

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
if [[ -z "$HEX_FILE" ]]; then
  for candidate in "${HEX_CANDIDATES[@]}"; do
    if [[ -f "$candidate" ]]; then
      # Normalise so the printed avrdude command has no ".." in it.
      HEX_FILE="$(cd "$(dirname "$candidate")" && pwd -P)/$(basename "$candidate")"
      break
    fi
  done
fi
[[ -n "$HEX_FILE" ]] || die "firmware image $HEX_BASENAME not found (looked in ${HEX_CANDIDATES[*]}); set HEX_FILE"
[[ -f "$HEX_FILE" ]] || die "firmware image not found: $HEX_FILE"
grep -q '^:00000001FF' "$HEX_FILE" || die "not an Intel HEX image: $HEX_FILE"

command -v "$AVRDUDE" >/dev/null 2>&1 || die "avrdude not found — run ./setup.sh first."
if [[ -n "$AVRDUDE_CONF" ]]; then
  [[ -f "$AVRDUDE_CONF" ]] || die "avrdude config not found: $AVRDUDE_CONF"
fi

[[ -w "$PORT" ]] || die "cannot open $PORT for writing — add your user to the port's group (Linux: dialout) and re-login"

# ---------------------------------------------------------------------------
# Build and run the avrdude command
# ---------------------------------------------------------------------------
CMD=("$AVRDUDE" -c "$PROGRAMMER" -P "$PORT" -p "$PART")
[[ -n "$AVRDUDE_CONF" ]] && CMD+=(-C "$AVRDUDE_CONF")
[[ -n "$BAUD" ]] && CMD+=(-b "$BAUD")
CMD+=(-e)
if [[ "$SKIP_FUSES" != 1 ]]; then
  for op in "${FUSE_OPS[@]}"; do
    CMD+=(-U "$op")
  done
fi
CMD+=(-U "flash:w:${HEX_FILE}:i")
[[ "$DRY_RUN" == 1 ]] && CMD+=(-n)

log "Flashing UPDIProgrammer firmware"
printf '    port:       %s\n' "$PORT"
printf '    image:      %s\n' "$HEX_FILE"
printf '    programmer: %s (part %s)\n' "$PROGRAMMER" "$PART"
if [[ "$SKIP_FUSES" == 1 ]]; then
  printf '    fuses:      kept (--no-fuses)\n'
else
  printf '    fuses:      chip erased, fuse0/1/2/4/5/6/7/8 rewritten\n'
fi
[[ "$DRY_RUN" == 1 ]] && printf '    dry run:    nothing will be written\n'
printf '    command:    '
printf '%q ' "${CMD[@]}"
printf '\n\n'

"${CMD[@]}"

printf '\n'
if [[ "$DRY_RUN" == 1 ]]; then
  echo "✅ Dry run complete — the chip was reachable, nothing was written."
else
  echo "✅ Firmware written to $PORT."
  echo "   Unplug/replug the board: it now runs jtag2updi and shows up as a"
  echo "   USB-serial programmer for the modules (modules/*/code/*/flash.sh)."
fi
