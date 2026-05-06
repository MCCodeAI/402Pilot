#!/usr/bin/env bash
# Sync paper/ to the sibling Overleaf clone and push to Overleaf.
#
# Why a sibling clone instead of git subtree:
# git subtree pull requires the prefix to have been added via `git subtree
# add`, which paper/ wasn't. Working around that requires history rewriting
# we don't want. Sibling clone + rsync is simpler and bullet-proof.
#
# One-time setup (run once, before first use):
#   cd ~/Documents/GitHub
#   git clone https://git@git.overleaf.com/69faa6c9c08812ba6863e6bb 402Pilot-overleaf
#
# Usage:
#   ./scripts/sync_paper_to_overleaf.sh "commit message here"
#   ./scripts/sync_paper_to_overleaf.sh                       # default msg

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER_DIR="$REPO_ROOT/paper/"
OVERLEAF_DIR="$(cd "$REPO_ROOT/.." && pwd)/402Pilot-overleaf"

if [ ! -d "$OVERLEAF_DIR/.git" ]; then
  cat <<EOF >&2
ERROR: $OVERLEAF_DIR is not a git clone.

First-time setup:
  cd "$(cd "$REPO_ROOT/.." && pwd)"
  git clone https://git@git.overleaf.com/69faa6c9c08812ba6863e6bb 402Pilot-overleaf

You'll be prompted for username (use 'git') and password (paste your
Overleaf Git Authentication Token).
EOF
  exit 1
fi

MSG="${1:-paper update from local}"

echo "==> rsync paper/ → $OVERLEAF_DIR"
rsync -av --delete --exclude='.git' "$PAPER_DIR" "$OVERLEAF_DIR/"

cd "$OVERLEAF_DIR"
echo "==> git add + commit in Overleaf clone"
git add -A
if git diff --cached --quiet; then
  echo "(nothing to commit — working tree clean)"
else
  git commit -m "$MSG"
fi

echo "==> git push to Overleaf"
git push origin master

echo
echo "✓ done — refresh Overleaf to see updates"
