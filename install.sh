#!/usr/bin/env bash

set -e

REPO_URL="https://github.com/aayushlalroy/axon.git"
PACKAGE_NAME="axon-cli"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Axon CLI Installation...${NC}"

# Check for pipx
if ! command -v pipx &> /dev/null; then
    echo -e "${RED}Error: 'pipx' is required for a safe installation but was not found.${NC}"
    echo -e "Please install pipx first:"
    echo -e "  macOS: ${YELLOW}brew install pipx${NC}"
    echo -e "  Ubuntu/Debian: ${YELLOW}sudo apt install pipx${NC}"
    echo -e "  Windows/Other: ${YELLOW}python3 -m pip install --user pipx${NC}"
    exit 1
fi

# Check if already installed
if pipx list --short | grep -q "^${PACKAGE_NAME} "; then
    echo -e "${YELLOW}Axon CLI is already installed. Updating to the latest version...${NC}"
    pipx install --force "git+${REPO_URL}"
else
    echo -e "${GREEN}Installing Axon CLI...${NC}"
    pipx install "git+${REPO_URL}"
fi

# Ensure pipx path is set
pipx ensurepath > /dev/null 2>&1

echo -e "\n${GREEN}Success! Axon CLI is ready to use.${NC}"
echo -e "Try running: ${YELLOW}axon --help${NC}"
