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

# ── Install / upgrade ─────────────────────────────────────────────────────────
section "Fetching and installing package"
"$ENV_DIR/bin/pip" install --quiet --upgrade pip

if [[ -n "$VERSION" ]]; then
    section "Installing Axon CLI @ ${VERSION}"
    "$ENV_DIR/bin/pip" install --quiet --upgrade "git+${REPO_URL}@${VERSION}"
elif [[ -f "pyproject.toml" ]]; then
    section "Installing Axon CLI from local workspace"
    "$ENV_DIR/bin/pip" install --quiet --upgrade -e .
else
    section "Installing / Updating Axon CLI (latest)"
    "$ENV_DIR/bin/pip" install --quiet --upgrade "git+${REPO_URL}"
fi

# ── Link executable ───────────────────────────────────────────────────────────
section "Linking executable"
mkdir -p "$BIN_DIR"
ln -sf "$ENV_DIR/bin/axon" "$BIN_DIR/axon"
info "Linked: $BIN_DIR/axon → $ENV_DIR/bin/axon"

INSTALLED_VERSION=$("$ENV_DIR/bin/axon" version 2>/dev/null || echo "unknown")
info "Installed version: $INSTALLED_VERSION"

# ── Configure default managed agents ───────────────────────────────────────
if [ -t 0 ] || [ -t 1 ]; then
    section "Default Agents Configuration"
    echo "Which agents do you want Axon to manage by default?"
    echo "  1. gemini (antigravity)"
    echo "  2. cursor"
    echo "  3. devin"
    echo "  4. windsurf"
    echo "  5. codex"
    echo "  6. copilot"
    read -r -p "Enter what all numbers do you want comma-separated no whitespace [Default: 1,2,3,4,5,6]: " SELECTED_AGENTS || SELECTED_AGENTS="1,2,3,4,5,6"
    SELECTED_AGENTS="${SELECTED_AGENTS:-1,2,3,4,5,6}"
    "$ENV_DIR/bin/python" -c "
import yaml
from pathlib import Path
axon_dir = Path.home() / '.axon'
axon_dir.mkdir(parents=True, exist_ok=True)
cfg_file = axon_dir / 'config.yaml'
cfg = {}
if cfg_file.exists():
    try:
        cfg = yaml.safe_load(cfg_file.read_text()) or {}
    except Exception:
        cfg = {}
mapping = {'1': 'gemini', '2': 'cursor', '3': 'devin', '4': 'windsurf', '5': 'codex', '6': 'copilot'}
raw = '$SELECTED_AGENTS'.split(',')
selected = [mapping[r.strip()] for r in raw if r.strip() in mapping]
if not selected:
    selected = list(mapping.values())
cfg['enabled_agents'] = selected
cfg_file.write_text(yaml.dump(cfg, default_flow_style=False))
print('[axon] Saved default enabled agents:', ', '.join(selected))
"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Axon CLI installed successfully!${NC}"

echo ""
echo "  axon --help        show all commands"
echo "  axon version       show installed version"
echo "  axon agents        list supported AI agents"
echo ""
