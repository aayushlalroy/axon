#!/usr/bin/env bash
# =============================================================================
# Axon CLI — Install / Update Script
#
# Works on macOS and Linux.
# Re-running this script also updates an existing installation.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh | bash
#   bash install.sh                    # install latest
#   bash install.sh --version v0.2.0  # install specific tag/branch
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/aayushlalroy/axon.git"
ENV_DIR="$HOME/.axon-env"
BIN_DIR="$HOME/.local/bin"
VERSION="${AXON_VERSION:-}"   # optionally override via env var

# Parse --version flag
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${GREEN}[axon]${NC} $*"; }
warn()    { echo -e "${YELLOW}[axon] Warning:${NC} $*"; }
error()   { echo -e "${RED}[axon] Error:${NC} $*" >&2; exit 1; }
section() { echo -e "\n${BOLD}▸ $*${NC}"; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
section "Pre-flight checks"

if ! command -v python3 &>/dev/null; then
    error "'python3' is required but was not found. Install Python 3.9+ and retry."
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 ]] || ( [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 9 ]] ); then
    error "Python 3.9+ is required. Found Python $PY_VERSION."
fi

info "Python $PY_VERSION — OK"

# ── Determine install target ──────────────────────────────────────────────────
if [[ -n "$VERSION" ]]; then
    INSTALL_TARGET="git+${REPO_URL}@${VERSION}"
    section "Installing Axon CLI @ ${VERSION}"
else
    INSTALL_TARGET="git+${REPO_URL}"
    section "Installing / Updating Axon CLI (latest)"
fi

# ── Create/reuse isolated venv ────────────────────────────────────────────────
section "Setting up isolated environment"

if [[ -d "$ENV_DIR" ]]; then
    info "Reusing existing environment at $ENV_DIR"
else
    info "Creating new environment at $ENV_DIR"
fi

python3 -m venv "$ENV_DIR"

# ── Install / upgrade ─────────────────────────────────────────────────────────
section "Fetching and installing package"
"$ENV_DIR/bin/pip" install --quiet --upgrade pip
"$ENV_DIR/bin/pip" install --quiet --upgrade "$INSTALL_TARGET"

# ── Link executable ───────────────────────────────────────────────────────────
section "Linking executable"
mkdir -p "$BIN_DIR"
ln -sf "$ENV_DIR/bin/axon" "$BIN_DIR/axon"
info "Linked: $BIN_DIR/axon → $ENV_DIR/bin/axon"

INSTALLED_VERSION=$("$ENV_DIR/bin/axon" version 2>/dev/null || echo "unknown")
info "Installed version: $INSTALLED_VERSION"

# ── PATH check ────────────────────────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    echo ""
    echo "  Add this line to your ~/.zshrc or ~/.bash_profile:"
    echo ""

    SHELL_NAME=$(basename "${SHELL:-bash}")
    case "$SHELL_NAME" in
        zsh)   echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc" ;;
        bash)  echo "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bash_profile && source ~/.bash_profile" ;;
        *)     echo "    export PATH=\"$BIN_DIR:\$PATH\"" ;;
    esac
    echo ""
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Axon CLI installed successfully!${NC}"
echo ""
echo "  axon --help        show all commands"
echo "  axon version       show installed version"
echo "  axon agents        list supported AI agents"
echo ""
