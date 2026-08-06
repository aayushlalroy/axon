#!/usr/bin/env bash

set -e

REPO_URL="https://github.com/aayushlalroy/axon.git"
ENV_DIR="$HOME/.axon-env"
BIN_DIR="$HOME/.local/bin"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Axon CLI Installation...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: 'python3' is required but was not found.${NC}"
    exit 1
fi

echo -e "${YELLOW}Setting up isolated environment in ${ENV_DIR}...${NC}"
# Use the built-in venv module to create a safe, isolated python environment
python3 -m venv "$ENV_DIR"

echo -e "${YELLOW}Installing/Updating Axon CLI from GitHub...${NC}"
# Use the isolated pip to install directly from git, forcing upgrade if already installed
"$ENV_DIR/bin/pip" install --upgrade "git+${REPO_URL}"

echo -e "${YELLOW}Creating executable link...${NC}"
mkdir -p "$BIN_DIR"

# Force symlink the executable to the local bin directory
ln -sf "$ENV_DIR/bin/axon" "$BIN_DIR/axon"

echo -e "\n${GREEN}Success! Axon CLI is installed.${NC}"

# Warn the user if ~/.local/bin is not in their system PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${YELLOW}Warning: $BIN_DIR is not in your PATH.${NC}"
    echo -e "You may need to add this line to your ~/.zshrc or ~/.bash_profile:"
    echo -e "  export PATH=\"$BIN_DIR:\$PATH\""
fi

echo -e "\nTo get started, try running: ${YELLOW}axon --help${NC}"
