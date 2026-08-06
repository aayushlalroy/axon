#!/usr/bin/env bash
# =============================================================================
# Axon CLI — Uninstall Script
#
# Removes the Axon CLI executable and its isolated Python environment.
# Optionally removes the global staging hub (~/.axon).
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/uninstall.sh | bash
#   bash uninstall.sh --keep-data    # keep ~/.axon staging hub
#   bash uninstall.sh --purge        # remove everything including ~/.axon
# =============================================================================

set -euo pipefail

ENV_DIR="$HOME/.axon-env"
BIN_LINK="$HOME/.local/bin/axon"
AXON_DATA="$HOME/.axon"

KEEP_DATA=false
PURGE=false

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep-data)  KEEP_DATA=true; shift ;;
        --purge)      PURGE=true;     shift ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: uninstall.sh [--keep-data | --purge]"
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
removed() { echo -e "${RED}[axon] Removed:${NC} $*"; }

echo -e "${BOLD}Axon CLI Uninstaller${NC}"
echo ""

# ── Remove executable symlink ─────────────────────────────────────────────────
if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    removed "$BIN_LINK"
else
    warn "Executable not found at $BIN_LINK — skipping."
fi

# ── Remove isolated venv ──────────────────────────────────────────────────────
if [ -d "$ENV_DIR" ]; then
    rm -rf "$ENV_DIR"
    removed "$ENV_DIR"
else
    warn "Environment not found at $ENV_DIR — skipping."
fi

# ── Handle staging hub ────────────────────────────────────────────────────────
if [ -d "$AXON_DATA" ]; then
    if $PURGE; then
        rm -rf "$AXON_DATA"
        removed "$AXON_DATA (--purge flag set)"
    elif $KEEP_DATA; then
        info "Keeping staging hub at $AXON_DATA (--keep-data flag set)"
    else
        # Interactive prompt — but guard against non-interactive shells (piped installs)
        if [ -t 0 ]; then
            echo ""
            echo -e "${YELLOW}Your staging hub ($AXON_DATA) contains your staged skills, principles,"
            echo -e "and workflows. Removing it is irreversible.${NC}"
            echo ""
            read -r -p "Remove staging hub (~/.axon)? [y/N]: " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                rm -rf "$AXON_DATA"
                removed "$AXON_DATA"
            else
                info "Kept staging hub at $AXON_DATA"
            fi
        else
            # Running non-interactively (e.g. piped from curl) — always keep data
            info "Non-interactive shell detected. Keeping staging hub at $AXON_DATA"
            info "Run 'rm -rf $AXON_DATA' manually if you want to remove it."
        fi
    fi
fi

echo ""
echo -e "${GREEN}${BOLD}✓ Axon CLI has been uninstalled.${NC}"
echo ""
