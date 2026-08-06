#!/usr/bin/env bash

set -e

ENV_DIR="$HOME/.axon-env"
BIN_LINK="$HOME/.local/bin/axon"
AXON_DIR="$HOME/.axon"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Axon CLI Uninstallation...${NC}"

# Remove the CLI executable symlink
if [ -L "$BIN_LINK" ] || [ -f "$BIN_LINK" ]; then
    rm -f "$BIN_LINK"
    echo -e "${GREEN}Removed ${BIN_LINK}${NC}"
fi

# Remove the isolated Python environment
if [ -d "$ENV_DIR" ]; then
    rm -rf "$ENV_DIR"
    echo -e "${GREEN}Removed ${ENV_DIR}${NC}"
fi

# Remove global staging configuration folder if requested
if [ -d "$AXON_DIR" ]; then
    read -p "Do you also want to remove global staging hub (~/.axon)? [y/N]: " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$AXON_DIR"
        echo -e "${GREEN}Removed ${AXON_DIR}${NC}"
    else
        echo -e "${YELLOW}Kept ${AXON_DIR}${NC}"
    fi
fi

echo -e "\n${GREEN}Success! Axon CLI has been uninstalled.${NC}"
