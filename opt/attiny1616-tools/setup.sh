#!/usr/bin/env bash
#
# setup.sh — one-time setup for compiling & flashing this ATtiny1616 firmware
# WITHOUT PlatformIO or VSCode. Uses arduino-cli + megaTinyCore.
#
# Safe to re-run. No Homebrew required.
#
set -euo pipefail

BIN_DIR="$HOME/bin"
ARDUINO_CLI="$BIN_DIR/arduino-cli"
INDEX_URL="http://drazzy.com/package_drazzy.com_index.json"
CORE_ID="megaTinyCore:megaavr"

echo "==> Ensuring ~/bin is on PATH"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  export PATH="$BIN_DIR:$PATH"
fi

# --- 1. Install arduino-cli (standalone binary, no brew) ---------------------
if [[ -x "$ARDUINO_CLI" ]]; then
  echo "==> arduino-cli already installed: $("$ARDUINO_CLI" version | head -1)"
else
  echo "==> Downloading arduino-cli..."
  mkdir -p "$BIN_DIR"
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64)
      URL="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_ARM64.tar.gz"
      ;;
    x86_64)
      URL="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_64bit.tar.gz"
      ;;
    *)
      echo "Unsupported architecture: $ARCH" >&2
      exit 1
      ;;
  esac
  curl -fsSL "$URL" -o "$BIN_DIR/arduino-cli.tar.gz"
  tar xzf "$BIN_DIR/arduino-cli.tar.gz" -C "$BIN_DIR" arduino-cli
  chmod +x "$ARDUINO_CLI"
  rm -f "$BIN_DIR/arduino-cli.tar.gz"
  echo "==> Installed: $("$ARDUINO_CLI" version | head -1)"
fi

# --- 2. Persist ~/bin on PATH (zsh + bash) -----------------------------------
for rc in "$HOME/.zshrc" "$HOME/.bash_profile"; do
  if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$rc" 2>/dev/null; then
    {
      echo ''
      echo '# arduino-cli (added by setup.sh)'
      echo 'export PATH="$HOME/bin:$PATH"'
    } >> "$rc"
    echo "==> Added ~/bin to PATH in $rc"
  fi
done

# --- 3. Register the megaTinyCore board index --------------------------------
CONFIG_FILE="$HOME/Library/Arduino15/arduino-cli.yaml"
if [[ -f "$CONFIG_FILE" ]] && grep -q 'drazzy.com' "$CONFIG_FILE" 2>/dev/null; then
  echo "==> megaTinyCore index already configured"
else
  echo "==> Registering megaTinyCore board index ($INDEX_URL)"
  "$ARDUINO_CLI" config add board_manager.additional_urls "$INDEX_URL"
fi

# --- 4. Install the megaTinyCore board package -------------------------------
echo "==> Updating board index..."
"$ARDUINO_CLI" core update-index

if "$ARDUINO_CLI" core list | grep -q '^megaTinyCore:megaavr'; then
  echo "==> megaTinyCore already installed"
else
  echo "==> Installing $CORE_ID (this downloads avr-gcc + avrdude, ~60 MB)..."
  "$ARDUINO_CLI" core install "$CORE_ID"
fi

echo ""
echo "✅ Setup complete."
echo "   Next: ./compile.sh   (build)"
echo "         ./flash.sh     (upload via UPDI)"
