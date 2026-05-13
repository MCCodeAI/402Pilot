#!/usr/bin/env bash
# Sync paper/ to the sibling Overleaf clone and push to Overleaf.
#
# WHY A SIBLING CLONE (NOT A GIT REMOTE ON THE MAIN REPO):
#   1. Overleaf has a FLAT structure (sections/, figures/, *.tex at the repo
#      root). The main 402Pilot repo nests the paper under paper/. Pushing
#      main → overleaf master corrupts one side or the other; pulling
#      overleaf master into main poisons the index and the working tree.
#   2. Overleaf prohibits force-push (server-side policy). So even if the
#      structures matched, --force / --force-with-lease will be rejected.
#
#   Both have been verified the hard way. Do NOT add an 'overleaf' git
#   remote to the main repo — this script warns if one re-appears.
#
# FIRST-TIME SETUP:
#   cd ~/Documents/GitHub
#   git clone https://git@git.overleaf.com/69faa6c9c08812ba6863e6bb 402Pilot-overleaf
#   (username 'git', password is your Overleaf Git Authentication Token:
#    Account Settings → Project sync → Git Integration → New Token)
#
# USAGE:
#   ./scripts/sync_paper_to_overleaf.sh "commit message"
#   ./scripts/sync_paper_to_overleaf.sh                          # default msg
#   ./scripts/sync_paper_to_overleaf.sh --dry-run "message"      # preview only
#
# WHAT HAPPENS:
#   1. Pre-flight: verify sibling clone exists; warn if the broken 'overleaf'
#      remote has been re-added to the main repo.
#   2. Fetch + fast-forward pull the sibling from Overleaf (captures any web-
#      editor commits since last sync).
#   3. Rsync paper/ → sibling with --delete (intentionally OVERWRITES any
#      Overleaf-only changes that aren't in local paper/).
#   4. Commit + push the resulting state to Overleaf master.
#
# "Overwriting Overleaf" is achieved by adding one new commit on top of
# Overleaf's history, NOT by force-pushing. The web-editor commits stay in
# Overleaf's git history; the working tree just reverts to match local.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER_DIR="$REPO_ROOT/paper/"
OVERLEAF_DIR="$(cd "$REPO_ROOT/.." && pwd)/402Pilot-overleaf"

# --- Parse args -------------------------------------------------------------
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi
MSG="${1:-paper update from local}"

# --- Pre-flight 1: sibling clone exists ------------------------------------
if [ ! -d "$OVERLEAF_DIR/.git" ]; then
  cat <<EOF >&2
ERROR: $OVERLEAF_DIR is not a git clone.

First-time setup:
  cd "$(cd "$REPO_ROOT/.." && pwd)"
  git clone https://git@git.overleaf.com/69faa6c9c08812ba6863e6bb 402Pilot-overleaf

You'll be prompted for username (use 'git') and password (paste your
Overleaf Git Authentication Token from Account Settings → Project sync).
EOF
  exit 1
fi

# --- Pre-flight 2: warn if broken overleaf remote re-appeared --------------
if git -C "$REPO_ROOT" remote get-url overleaf >/dev/null 2>&1; then
  cat <<EOF >&2
WARNING: Main repo has an 'overleaf' git remote configured. This DOES NOT
WORK (structure mismatch + Overleaf prohibits force-push) and has corrupted
the index in the past. Remove it:

  git -C "$REPO_ROOT" remote remove overleaf

Continuing with sibling-clone sync...

EOF
fi

# --- Step 1: sync sibling with Overleaf so push is fast-forward ------------
echo "==> fetching Overleaf state into sibling clone"
cd "$OVERLEAF_DIR"
git fetch origin --quiet

LOCAL_HEAD=$(git rev-parse master 2>/dev/null || echo "")
REMOTE_HEAD=$(git rev-parse origin/master 2>/dev/null || echo "")

if [ -n "$LOCAL_HEAD" ] && [ -n "$REMOTE_HEAD" ] && [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  AHEAD=$(git rev-list --count "master..origin/master" 2>/dev/null || echo "?")
  BEHIND=$(git rev-list --count "origin/master..master" 2>/dev/null || echo "?")
  echo "    sibling vs Overleaf: behind=$AHEAD, ahead=$BEHIND"
  if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then
    echo "    pulling Overleaf changes into sibling (fast-forward only)..."
    git pull --ff-only origin master
  fi
fi

# --- Step 2: rsync paper/ → sibling ---------------------------------------
# Excludes: .git (sibling has its own), .DS_Store (macOS clutter), and LaTeX
# build artifacts (Overleaf regenerates on its own).
RSYNC_FLAGS=(
  -av --delete
  --exclude='.git'
  --exclude='.DS_Store'
  --exclude='*.aux'
  --exclude='*.bbl'
  --exclude='*.blg'
  --exclude='*.log'
  --exclude='*.out'
  --exclude='*.toc'
  --exclude='*.lof'
  --exclude='*.lot'
  --exclude='*.fls'
  --exclude='*.fdb_latexmk'
  --exclude='*.synctex.gz'
  --exclude='*.pdf'
)

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "==> [DRY-RUN] rsync paper/ → $OVERLEAF_DIR (no files written)"
  rsync "${RSYNC_FLAGS[@]}" --dry-run "$PAPER_DIR" "$OVERLEAF_DIR/"
  echo
  echo "==> [DRY-RUN] would commit with: \"$MSG\""
  echo "==> [DRY-RUN] would push to: origin master"
  exit 0
fi

echo
echo "==> rsync paper/ → $OVERLEAF_DIR"
rsync "${RSYNC_FLAGS[@]}" "$PAPER_DIR" "$OVERLEAF_DIR/"

# --- Step 3: commit + push -------------------------------------------------
cd "$OVERLEAF_DIR"
echo "==> git add + commit in Overleaf clone"
git add -A
if git diff --cached --quiet; then
  echo "    (nothing to commit — sibling already matches local paper/)"
  echo
  echo "✓ done (no changes to sync)"
  exit 0
fi
git commit -m "$MSG"

echo "==> git push to Overleaf"
git push origin master

echo
echo "✓ done — refresh Overleaf to see updates"
