#!/usr/bin/env bash
set -euo pipefail

REPO="yukai08008/agenty"
BIN_NAME="agenty"
INSTALL_DIR="${HOME}/.local/bin"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[agenty]${NC} $*"; }
warn()  { echo -e "${YELLOW}[agenty]${NC} $*"; }
error() { echo -e "${RED}[agenty]${NC} $*" >&2; exit 1; }

# --- Ensure uv is installed ---
ensure_uv() {
  if command -v uv &>/dev/null; then
    return
  fi

  info "uv not found, installing..."
  curl -fsSL https://astral.sh/uv/install.sh | sh

  # Source the shell profile so uv is available in this session
  for profile in "${HOME}/.bashrc" "${HOME}/.zshrc" "${HOME}/.profile"; do
    if [ -f "$profile" ]; then
      # shellcheck disable=SC1090
      source "$profile" 2>/dev/null || true
    fi
  done

  command -v uv &>/dev/null || error "uv installation failed. Please install uv manually: https://docs.astral.sh/uv/"
}

# --- Ensure install dir exists and is in PATH ---
ensure_path() {
  mkdir -p "$INSTALL_DIR"

  case ":${PATH}:" in
    *:"${INSTALL_DIR}":*) return ;;
  esac

  # Detect shell config file
  local rc_file=""
  if [ -n "${ZSH_VERSION:-}" ]; then
    rc_file="${HOME}/.zshrc"
  elif [ -n "${BASH_VERSION:-}" ]; then
    rc_file="${HOME}/.bashrc"
  else
    rc_file="${HOME}/.profile"
  fi

  warn "$INSTALL_DIR is not in PATH, adding to $rc_file"
  echo '' >> "$rc_file"
  echo 'export PATH="'${INSTALL_DIR}':$PATH"' >> "$rc_file"
  export PATH="${INSTALL_DIR}:$PATH"
}

# --- Install agenty via uv tool ---
install_agenty() {
  info "Installing ${BIN_NAME} via uv..."
  uv tool install "git+https://github.com/${REPO}.git" --force

  # Verify
  if command -v "$BIN_NAME" &>/dev/null; then
    info "Successfully installed! Version: $(${BIN_NAME} --version 2>&1 || echo 'unknown')"
    info "Run '${BIN_NAME} --help' to get started."
  else
    # uv tool install puts binaries in ~/.local/bin, ensure it's in PATH
    if [ -f "${INSTALL_DIR}/${BIN_NAME}" ]; then
      warn "${BIN_NAME} installed but not in current PATH."
      warn "Please restart your terminal or run: source ~/.zshrc (or ~/.bashrc)"
    else
      error "Installation failed. Please check the output above."
    fi
  fi
}

# --- Uninstall ---
uninstall_agenty() {
  info "Uninstalling ${BIN_NAME}..."
  uv tool uninstall "$BIN_NAME" 2>/dev/null || true
  rm -f "${INSTALL_DIR}/${BIN_NAME}"
  info "Uninstalled successfully."
}

# --- Main ---
main() {
  echo ""
  echo "  ___              _   "
  echo " / _ \\ _ __   ___ | |_ "
  echo "| |_| | '_ \\ / _ \\| __|"
  echo "|  _  | | | | (_) | |_ "
  echo "|_| |_|_| |_|\\___/ \\__|"
  echo ""
  echo "  A demo agent CLI built with uv"
  echo ""

  if [ "${1:-}" = "uninstall" ]; then
    uninstall_agenty
    return
  fi

  ensure_uv
  ensure_path
  install_agenty
}

main "$@"
