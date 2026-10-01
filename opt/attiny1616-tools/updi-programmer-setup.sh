#!/usr/bin/env bash
#
# updi-programmer-setup.sh — one-time setup for flashing the UPDIProgrammer
# firmware (jtag2updi on an ATtiny1616) through a USB-serial UPDI adapter.
#
# Shared tool: projects symlink it, e.g.
#   opt/UPDIProgrammer/firmware/setup.sh -> ../../attiny1616-tools/updi-programmer-setup.sh
#
# It makes sure an avrdude that can drive jtag2updi is available, in this order:
#   1. reuse an avrdude that is already installed and supports jtag2updi;
#   2. install it with the system package manager (brew / apt-get / dnf / pacman
#      / zypper);
#   3. fall back to arduino-cli + megaTinyCore — the same approach as the
#      opt/attiny1616-tools/setup.sh that the 8bit module uses — and expose the
#      bundled avrdude as ~/bin/avrdude. An avrdude 6.3 build only knows
#      jtag2updi when megaTinyCore's avrdude.conf is loaded, hence the wrapper.
#
# Finally it checks that the serial port can be opened by this user (Linux:
# membership of the port's group, usually dialout).
#
# Safe to re-run (idempotent). No Homebrew required.
#
# Usage:
#   ./setup.sh            install whatever is missing
#   ./setup.sh --check    report the current state only; change nothing
#
set -euo pipefail

BIN_DIR="${BIN_DIR:-$HOME/bin}"
AVRDUDE_WRAPPER="$BIN_DIR/avrdude"
INDEX_URL="http://drazzy.com/package_drazzy.com_index.json"
CORE_ID="megaTinyCore:megaavr"
PORT_DEFAULT="${PORT_DEFAULT:-/dev/ttyUSB0}"
BOARD_NAME="Bread Modular UPDIProgrammer"

log()  { printf '==> %s\n' "$*"; }
warn() { printf 'Warning: %s\n' "$*" >&2; }
die()  { printf 'Error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
setup.sh — install what is needed to flash the UPDIProgrammer firmware.

Usage:
  ./setup.sh            install the missing pieces (avrdude + serial access)
  ./setup.sh --check    report the current state only; change nothing
  ./setup.sh -h         this help
EOF
}

CHECK_ONLY=0
parse_args() {
  CHECK_ONLY=0
  case "${1:-}" in
    "") ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  [[ $# -le 1 ]] || die "unexpected arguments: ${*:2}"
}

export PATH="$BIN_DIR:$PATH"

# ---------------------------------------------------------------------------
# avrdude inspection helpers
# ---------------------------------------------------------------------------
avrdude_major() {
  "$1" -v 2>&1 | grep -oiE 'version [0-9]+' | grep -oE '[0-9]+' | head -1 || true
}

# avrdude >= 7 knows jtag2updi natively; older 6.3 builds only when the loaded
# configuration file declares the programmer (megaTinyCore's does). Ask avrdude
# itself instead of guessing: hand it a programmer id that does not exist and
# read the "Valid programmers are:" list it prints.
avrdude_supports_jtag2updi() {
  local bin="$1"; shift
  [[ -x "$bin" || -n "$(command -v "$bin" 2>/dev/null || true)" ]] || return 1
  local out count
  # Note: no `| grep -q` here — grep exits on the first match, avrdude would die
  # from SIGPIPE, and `set -o pipefail` would then report a false negative.
  out="$("$bin" "$@" -c __probe__ 2>&1 || true)"
  count="$(printf '%s\n' "$out" | grep -cE '^ *jtag2updi ' || true)"
  [[ "${count:-0}" -ge 1 ]]
}

# Print the path of an avrdude that can drive jtag2updi, if there is one.
usable_avrdude() {
  local bin
  for bin in "$AVRDUDE_WRAPPER" avrdude; do
    if [[ -x "$bin" || -n "$(command -v "$bin" 2>/dev/null || true)" ]] \
       && avrdude_supports_jtag2updi "$bin"; then
      command -v "$bin" 2>/dev/null || printf '%s\n' "$bin"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# Installer 1: the system package manager
# ---------------------------------------------------------------------------
as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "root privileges are needed to run: $*"
  fi
}

install_with_package_manager() {
  if command -v brew >/dev/null 2>&1; then
    log "Installing avrdude with Homebrew"
    brew install avrdude
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1; then
    log "Installing avrdude with apt-get"
    as_root apt-get update -qq
    as_root apt-get install -y avrdude
    return 0
  fi
  if command -v dnf >/dev/null 2>&1; then
    log "Installing avrdude with dnf"
    as_root dnf install -y avrdude
    return 0
  fi
  if command -v pacman >/dev/null 2>&1; then
    log "Installing avrdude with pacman"
    as_root pacman -Sy --noconfirm avrdude
    return 0
  fi
  if command -v zypper >/dev/null 2>&1; then
    log "Installing avrdude with zypper"
    as_root zypper --non-interactive install avrdude
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Installer 2: arduino-cli + megaTinyCore (no Homebrew, same as the 8bit module)
# ---------------------------------------------------------------------------
arduino_cli_bin() {
  if [[ -x "$BIN_DIR/arduino-cli" ]]; then
    printf '%s\n' "$BIN_DIR/arduino-cli"
    return 0
  fi
  if command -v arduino-cli >/dev/null 2>&1; then
    command -v arduino-cli
    return 0
  fi
  return 1
}

download_arduino_cli() {
  local url
  case "$(uname -s)/$(uname -m)" in
    Linux/x86_64)              url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_64bit.tar.gz" ;;
    Linux/aarch64|Linux/arm64) url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_Linux_ARM64.tar.gz" ;;
    Darwin/arm64)              url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_ARM64.tar.gz" ;;
    Darwin/x86_64)             url="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_64bit.tar.gz" ;;
    *) die "no arduino-cli download for $(uname -s)/$(uname -m)" ;;
  esac
  command -v curl >/dev/null 2>&1 || die "curl is required to download arduino-cli"
  log "Downloading arduino-cli into $BIN_DIR"
  mkdir -p "$BIN_DIR"
  curl -fsSL "$url" -o "$BIN_DIR/arduino-cli.tar.gz"
  tar xzf "$BIN_DIR/arduino-cli.tar.gz" -C "$BIN_DIR" arduino-cli
  chmod +x "$BIN_DIR/arduino-cli"
  rm -f "$BIN_DIR/arduino-cli.tar.gz"
}

find_bundled_avrdude() {
  local p
  for p in "$HOME/.arduino15/packages/arduino/tools/avrdude"/*/bin/avrdude \
           "$HOME/Library/Arduino15/packages/arduino/tools/avrdude"/*/bin/avrdude; do
    [[ -x "$p" ]] && { printf '%s\n' "$p"; return 0; }
  done
  return 1
}

find_megatinycore_conf() {
  local p
  for p in "$HOME/.arduino15/packages/megaTinyCore/hardware/megaavr"/*/avrdude.conf \
           "$HOME/Library/Arduino15/packages/megaTinyCore/hardware/megaavr"/*/avrdude.conf; do
    [[ -f "$p" ]] && { printf '%s\n' "$p"; return 0; }
  done
  return 1
}

install_via_arduino_cli() {
  local cli
  if ! cli="$(arduino_cli_bin)"; then
    download_arduino_cli
    cli="$BIN_DIR/arduino-cli"
  else
    log "Using the existing arduino-cli: $cli"
  fi

  log "Registering the megaTinyCore board index"
  "$cli" config add board_manager.additional_urls "$INDEX_URL" >/dev/null 2>&1 || true
  "$cli" core update-index

  if "$cli" core list 2>/dev/null | grep -q '^megaTinyCore:megaavr'; then
    log "megaTinyCore is already installed"
  else
    log "Installing $CORE_ID (downloads the megaAVR toolchain + avrdude, ~60 MB)"
    "$cli" core install "$CORE_ID"
  fi
}

install_avrdude_wrapper() {
  local bin conf
  bin="$(find_bundled_avrdude)" || die "arduino-cli did not install an avrdude binary"
  conf="$(find_megatinycore_conf)" || die "the megaTinyCore avrdude.conf was not found"
  mkdir -p "$BIN_DIR"
  {
    printf '#!/usr/bin/env bash\n'
    printf '# Generated by opt/attiny1616-tools/updi-programmer-setup.sh\n'
    printf '# avrdude from the megaTinyCore package: its avrdude.conf declares the\n'
    printf '# jtag2updi programmer (needed by 6.3 builds).\n'
    printf 'exec %q -C %q "$@"\n' "$bin" "$conf"
  } > "$AVRDUDE_WRAPPER"
  chmod +x "$AVRDUDE_WRAPPER"
  log "Created $AVRDUDE_WRAPPER"
}

# ~/bin must be on PATH for the wrapper to be found by flash.sh.
ensure_bin_on_path() {
  local rc
  for rc in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.profile"; do
    [[ -f "$rc" ]] || continue
    if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$rc" 2>/dev/null; then
      {
        printf '\n'
        printf '# avrdude (added by updi-programmer-setup.sh)\n'
        printf 'export PATH="$HOME/bin:$PATH"\n'
      } >> "$rc"
      log "Added ~/bin to PATH in $rc"
    fi
  done
}

install_avrdude() {
  if install_with_package_manager; then
    command -v avrdude >/dev/null 2>&1 && avrdude_supports_jtag2updi avrdude && return 0
    warn "the avrdude the package manager installed cannot drive jtag2updi; falling back to arduino-cli + megaTinyCore"
  else
    log "No supported package manager found; using arduino-cli + megaTinyCore instead"
  fi

  install_via_arduino_cli
  install_avrdude_wrapper
  ensure_bin_on_path
  export PATH="$BIN_DIR:$PATH"
  avrdude_supports_jtag2updi "$AVRDUDE_WRAPPER"
}

# ---------------------------------------------------------------------------
# Serial port access
# ---------------------------------------------------------------------------
check_serial_access() {
  local dev grp
  dev="$PORT_DEFAULT"
  if [[ ! -e "$dev" ]]; then
    log "No serial port at $dev right now (plug the UPDI adapter in later; flash.sh lists the ports)"
    return 0
  fi
  if [[ -r "$dev" && -w "$dev" ]]; then
    log "Serial port $dev is accessible"
    return 0
  fi

  warn "this user cannot open $dev"
  [[ "$(uname -s)" == Linux ]] || return 1
  grp="$(stat -c '%G' "$dev" 2>/dev/null || printf 'dialout\n')"
  if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx "$grp"; then
    warn "you are already in '$grp'; check the udev rules / unplug and replug the adapter"
    return 1
  fi
  warn "add yourself to the '$grp' group, then log out and back in:"
  warn "  sudo usermod -aG $grp $USER"
  if command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
    log "Running that usermod for you (a re-login is still required)"
    as_root usermod -aG "$grp" "$USER" || warn "usermod failed; run it manually"
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  parse_args "$@"

  log "Setting up $BOARD_NAME firmware flashing on $(uname -s)/$(uname -m)"

  FOUND="$(usable_avrdude || true)"
  if [[ -n "$FOUND" ]]; then
    log "avrdude is already usable: $FOUND (version $(avrdude_major "$FOUND"))"
  else
    if [[ "$CHECK_ONLY" == 1 ]]; then
      warn "no avrdude with jtag2updi support found — re-run ./setup.sh without --check to install it"
      check_serial_access || true
      exit 1
    fi
    log "No usable avrdude found — installing one"
    if ! install_avrdude; then
      die "could not provide an avrdude with jtag2updi support"
    fi
    FOUND="$(usable_avrdude || true)"
    [[ -n "$FOUND" ]] || die "avrdude installation did not work out"
    log "avrdude ready: $FOUND (version $(avrdude_major "$FOUND"))"
  fi

  check_serial_access || true

  echo ""
  echo "✅ Setup complete."
  echo "   Flash the programmer firmware with:"
  echo "     ./flash.sh                 # pick the port from the list"
  echo "     ./flash.sh /dev/ttyUSB0    # or name it explicitly"
  echo "     ./flash.sh --dry-run       # check the wiring, write nothing"
}

# Run only when executed (not when sourced, e.g. by the tests).
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" ]]; then
  main "$@"
fi
