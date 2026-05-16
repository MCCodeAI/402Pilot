# Overleaf Sync — How and Why

This is the runbook for keeping `402Pilot/paper/` in sync with the Overleaf
project. **Read this before improvising any new git workflow with Overleaf** —
the obvious approaches all break in subtle ways and have wasted hours of
recovery work.

## TL;DR

```
# normal sync (local → Overleaf)
./scripts/sync_paper_to_overleaf.sh "your commit message"

# preview without pushing
./scripts/sync_paper_to_overleaf.sh --dry-run "your commit message"
```

That's it. The script handles fetching Overleaf's latest, rsyncing local
`paper/` over the sibling clone, committing, and pushing.

## Architecture

There are three repos / locations involved:

| Location | Path | Purpose | Structure |
|---|---|---|---|
| **Main repo** | `~/Documents/GitHub/402Pilot/` | Code + paper + scripts. Pushes to `origin` (GitHub). | Nested: paper lives at `paper/` |
| **Sibling clone** | `~/Documents/GitHub/402Pilot-overleaf/` | Mirror of the Overleaf project. Pushes to Overleaf master. | Flat: paper at root |
| **Overleaf** | `git.overleaf.com/6a082432eb43ebce16b669d0` | Where co-authors edit via web editor. | Flat: paper at root |

The sync script is the bridge between the main repo and the sibling clone.
GitHub gets the full main repo; Overleaf gets only the paper, flattened.

## Why a sibling clone (not a git remote)

Two independent reasons make the "just add `overleaf` as a git remote on the
main repo" approach unworkable. Both have been verified the hard way.

### Reason 1: structure mismatch

Overleaf's repo is **flat** — `sections/`, `figures/`, `main.tex`,
`references.bib` all live at the repo root. The main 402Pilot repo nests
those under `paper/`, alongside `pilot402/`, `tests/`, `scripts/`, etc.

If you try `git push overleaf main:master`, you push the whole main repo
(code directories included) to Overleaf, breaking its structure. If you try
`git pull overleaf master` into main, git reads Overleaf's flat tree into
the main repo's index — every `paper/X` becomes "deleted, new at `X`",
every code directory becomes "deleted". Index corruption, and depending on
where the pull fails, working-tree files can be lost.

### Reason 2: Overleaf prohibits force-push

Server-side policy: `git push --force` and `git push --force-with-lease`
both return:

```
remote: error: forced push prohibited
remote: hint: You can't git push --force to a Overleaf project.
```

So even if the structures matched, you can't overwrite Overleaf's web-editor
commits with a force-push. "Overwriting Overleaf" has to be done by adding a
new commit on top of Overleaf's history that reverts the web-editor state to
your local state. The sync script does exactly this via `rsync --delete` +
commit.

## First-time setup

If `~/Documents/GitHub/402Pilot-overleaf/` doesn't exist (sync script will
error and tell you):

```
cd ~/Documents/GitHub
git clone https://git@git.overleaf.com/6a082432eb43ebce16b669d0 402Pilot-overleaf
```

You'll be prompted for:
- **Username**: `git`
- **Password**: Overleaf Git Authentication Token (from
  Account Settings → Project sync → Git Integration → New Token)

The token gets cached by macOS Keychain; you won't be asked again.

## Common operations

### Normal sync: local edits → Overleaf

```
cd ~/Documents/GitHub/402Pilot
./scripts/sync_paper_to_overleaf.sh "describe what changed"
```

Default behavior is **local overwrites Overleaf**: any web-editor changes
since the last sync are erased (but stay in Overleaf's git history). If
you've been doing all the editing locally, this is what you want.

### Preview what would be synced

```
./scripts/sync_paper_to_overleaf.sh --dry-run "message"
```

Shows the rsync diff without writing anything. Good before a big sync.

### Pull Overleaf changes back to local

If a co-author edited in Overleaf and you want those changes locally:

```
git -C ~/Documents/GitHub/402Pilot-overleaf pull --ff-only origin master

cd ~/Documents/GitHub/402Pilot
rsync -av --delete --dry-run --exclude='.git' --exclude='.DS_Store' \
  ~/Documents/GitHub/402Pilot-overleaf/ paper/

rsync -av --delete --exclude='.git' --exclude='.DS_Store' \
  ~/Documents/GitHub/402Pilot-overleaf/ paper/

# review with `git diff paper/`
git add paper/ && git commit -m "pull Overleaf edits"
git push origin main
```

This direction overwrites local `paper/` with the current Overleaf project.
Use the dry run first if you have uncommitted local paper edits. Do **not**
run `git pull` from Overleaf inside the main repo; only pull inside the
sibling clone.

### Commit messages on Overleaf

The sync commit message goes into Overleaf's git history and shows up in
Overleaf's history panel. Keep it descriptive (`"§3 problem formulation:
make burn_dev signed"` not `"update"`).

## Failure modes and recovery

### "ERROR: ../402Pilot-overleaf is not a git clone"

Sibling clone doesn't exist. Do the first-time setup above.

### "remote: error: forced push prohibited"

You ran `git push --force` to Overleaf directly. Don't do that. Use the
sync script — it does fast-forward pushes only.

### "rejected (non-fast-forward)"

The sibling clone is behind Overleaf master. The sync script handles this
by running `git pull --ff-only` before pushing. If you ran git commands
manually instead of the script, just:

```
cd ~/Documents/GitHub/402Pilot-overleaf
git pull --ff-only origin master
```

then re-run the sync script.

### "cannot pull with rebase: Your index contains uncommitted changes" (in main repo)

Symptom of the broken `overleaf` git remote being used in the main repo —
a previous `git pull overleaf` poisoned the index. To recover:

```
cd ~/Documents/GitHub/402Pilot
git reset --hard HEAD       # working tree + index back to HEAD; untracked files survive
git remote remove overleaf  # remove the broken remote so it can't happen again
```

The sync script warns if this remote is detected.

### Working tree got switched to Overleaf's flat structure

(e.g. `sections/`, `main.tex` appear at main repo root; `paper/`,
`pilot402/` are gone from working tree.) This means a partial `git pull
overleaf` checkout completed before failing. Recover with:

```
git reset --hard HEAD
```

This restores HEAD's tree (nested, with paper/ and code intact).

### Two co-authors edited the same paragraph (one local, one on Overleaf)

The sync script's default behavior (local overwrites Overleaf) will discard
the Overleaf-side edit. If you want to keep it:

1. Pull Overleaf back to local first (manual procedure above).
2. Resolve the merge in your editor.
3. Then run the sync script.

## What the script does not do

- **Does not push to GitHub.** Run `git push origin main` from the main
  repo separately.
- **Does not commit your local paper/ edits.** Commit them in the main repo
  first (`git add paper/ && git commit`); the sync script just copies
  whatever's currently in `paper/` to the sibling.
- **Does not handle binary merge conflicts** (e.g. competing figure files).
  Resolve those manually in `paper/figures/` before sync.

## File exclusion list

The sync script excludes these patterns when rsyncing:

- `.git` — sibling has its own
- `.DS_Store` — macOS Finder metadata
- LaTeX build artifacts: `*.aux`, `*.bbl`, `*.blg`, `*.log`, `*.out`,
  `*.toc`, `*.lof`, `*.lot`, `*.fls`, `*.fdb_latexmk`, `*.synctex.gz`
- `*.pdf` — Overleaf compiles its own

If a co-author insists on a compiled PDF being on Overleaf, remove the
`*.pdf` exclude in the script. Otherwise leave it out.
