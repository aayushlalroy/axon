#!/usr/bin/env bash
# =============================================================================
# Axon CLI — Release Script
#
# Creates a new versioned release:
#   1. Bumps the version in pyproject.toml
#   2. Updates CHANGELOG.md with the release date
#   3. Commits, tags, and optionally pushes to GitHub
#
# Usage:
#   bash scripts/release.sh 0.3.0
#   bash scripts/release.sh 0.3.0 --push
#   bash scripts/release.sh 0.3.0 --dry-run
# =============================================================================

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
NEW_VERSION="${1:-}"
PUSH=false
DRY_RUN=false

if [[ -z "$NEW_VERSION" ]]; then
    echo "Usage: bash scripts/release.sh <version> [--push] [--dry-run]"
    echo "Example: bash scripts/release.sh 0.3.0 --push"
    exit 1
fi

shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --push)    PUSH=true;    shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info()   { echo -e "${GREEN}[release]${NC} $*"; }
warn()   { echo -e "${YELLOW}[release] Warning:${NC} $*"; }
run()    {
    echo -e "  ${BOLD}$ $*${NC}"
    if ! $DRY_RUN; then
        eval "$@"
    fi
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYPROJECT="$REPO_ROOT/pyproject.toml"
CHANGELOG="$REPO_ROOT/CHANGELOG.md"

cd "$REPO_ROOT"

# ── Validation ────────────────────────────────────────────────────────────────
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Version must be in semver format: MAJOR.MINOR.PATCH (e.g. 0.3.0)"
    exit 1
fi

TAG="v$NEW_VERSION"
CURRENT_VERSION=$(grep -E '^version = ' "$PYPROJECT" | sed 's/version = "//;s/"//')

if [[ "$CURRENT_VERSION" == "$NEW_VERSION" ]]; then
    warn "Version is already $NEW_VERSION in pyproject.toml."
fi

# Check working tree is clean
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is not clean. Commit or stash changes before releasing."
    exit 1
fi

info "Releasing axon-cli $CURRENT_VERSION → $NEW_VERSION"
$DRY_RUN && warn "DRY RUN — no files will be changed, no commits made."

# ── Bump version in pyproject.toml ───────────────────────────────────────────
info "Bumping version in pyproject.toml"
run "sed -i.bak 's/^version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/' \"$PYPROJECT\" && rm -f \"${PYPROJECT}.bak\""

# ── Update CHANGELOG.md ───────────────────────────────────────────────────────
TODAY=$(date +%Y-%m-%d)
info "Adding CHANGELOG entry for $TAG ($TODAY)"

CHANGELOG_ENTRY="## [$NEW_VERSION] — $TODAY\n\n### Added\n- (fill in)\n\n### Changed\n- (fill in)\n\n### Fixed\n- (fill in)\n\n"

if ! $DRY_RUN; then
    # Insert new entry after the first line (the # Changelog heading)
    TMP=$(mktemp)
    {
        head -n 1 "$CHANGELOG"
        echo ""
        printf "%b" "$CHANGELOG_ENTRY"
        tail -n +2 "$CHANGELOG"
    } > "$TMP"
    mv "$TMP" "$CHANGELOG"
fi

# ── Commit & tag ──────────────────────────────────────────────────────────────
info "Committing changes"
run "git add \"$PYPROJECT\" \"$CHANGELOG\""
run "git commit -m \"chore: release $TAG\""

info "Tagging $TAG"
run "git tag -a \"$TAG\" -m \"Release $TAG\""

# ── Optionally push ───────────────────────────────────────────────────────────
if $PUSH; then
    info "Pushing main and $TAG to origin"
    run "git push origin main"
    run "git push origin \"$TAG\""
    echo ""
    info "GitHub Actions will automatically create the GitHub Release."
    info "Users can now install this version with:"
    echo "  curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh | bash"
    echo "  # or pinned:"
    echo "  AXON_VERSION=$TAG bash <(curl -sSL https://raw.githubusercontent.com/aayushlalroy/axon/main/install.sh)"
else
    echo ""
    warn "Not pushing. Run with --push to publish, or push manually:"
    echo "  git push origin main && git push origin $TAG"
fi

echo ""
echo -e "${GREEN}${BOLD}✓ Release $TAG prepared successfully.${NC}"
