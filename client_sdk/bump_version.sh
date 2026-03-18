#!/usr/bin/env bash
set -euo pipefail

# Version Bump Script
# Updates version across all files and creates git tag

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <new-version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (semantic versioning)
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Invalid version format. Use semantic versioning (e.g., 0.2.0)"
    exit 1
fi

echo "=== Version Bump Script ==="
echo "New version: $NEW_VERSION"
echo ""

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: You have uncommitted changes"
    echo "Commit or stash them before bumping version"
    exit 1
fi

# Update pyproject.toml
echo "Updating pyproject.toml..."
sed -i.bak "s/^version = .*/version = \"$NEW_VERSION\"/" pyproject.toml
rm pyproject.toml.bak

# Update __init__.py
echo "Updating src/p2p_sdk/__init__.py..."
sed -i.bak "s/__version__ = .*/__version__ = \"$NEW_VERSION\"/" src/p2p_sdk/__init__.py
rm src/p2p_sdk/__init__.py.bak

# Update conda meta.yaml
echo "Updating conda/meta.yaml..."
sed -i.bak "s/{% set version = .* %}/{% set version = \"$NEW_VERSION\" %}/" conda/meta.yaml
rm conda/meta.yaml.bak

# Update CHANGELOG.md
echo "Updating CHANGELOG.md..."
TODAY=$(date +%Y-%m-%d)
sed -i.bak "s/## \[Unreleased\]/## [Unreleased]\n\n## [$NEW_VERSION] - $TODAY/" CHANGELOG.md
rm CHANGELOG.md.bak

echo ""
echo "Version updated to $NEW_VERSION"
echo ""
echo "Next steps:"
echo "1. Review changes: git diff"
echo "2. Update CHANGELOG.md with release notes"
echo "3. Commit changes: git add -A && git commit -m 'chore: bump version to $NEW_VERSION'"
echo "4. Create tag: git tag -a v$NEW_VERSION -m 'Release v$NEW_VERSION'"
echo "5. Push: git push && git push --tags"
