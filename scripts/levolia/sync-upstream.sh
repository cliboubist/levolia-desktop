#!/usr/bin/env bash
# Pull the latest Nous Research hermes-agent into the Levolia fork.
#
#   bash scripts/levolia/sync-upstream.sh
#
# 1. Fast-forwards local `main` to upstream/main (no Levolia changes live there).
# 2. Merges `main` into `levolia`.
# 3. On conflict, takes the upstream version of the high-churn text files
#    (desktop locales and their brand-string tests) and re-runs the rebrand
#    script. Any other conflict is left for you to resolve by hand.
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree not clean; commit or stash first." >&2
  exit 1
fi

git fetch upstream
git checkout -q main
git merge --ff-only upstream/main
git checkout -q levolia

if git merge --no-edit main; then
  python3 scripts/levolia/rebrand.py
  if [ -n "$(git status --porcelain)" ]; then
    git commit -qam "chore(levolia): re-apply rebrand after upstream sync"
  fi
  echo "Merged cleanly. Now: cd apps/desktop && npm install --prefix ../.. && npm run typecheck && npm run test:ui"
  exit 0
fi

echo "Merge has conflicts. Auto-resolving text files by taking upstream + rebrand…"
TEXT_FILES=$(git diff --name-only --diff-filter=U | grep -E '^apps/desktop/src/i18n/(en|ar|ja|zh|zh-hant|ru)\.ts$|\.test\.tsx?$' || true)
for f in $TEXT_FILES; do
  git checkout --theirs -- "$f"
  git add "$f"
done
python3 scripts/levolia/rebrand.py
git add -A apps/desktop/src/i18n apps/desktop/electron/main.ts 2>/dev/null || true

REMAINING=$(git diff --name-only --diff-filter=U || true)
if [ -n "$REMAINING" ]; then
  echo "Resolve these by hand, then: python3 scripts/levolia/rebrand.py && git add -A && git commit" >&2
  echo "$REMAINING" >&2
  exit 2
fi

git commit -q --no-edit
echo "Merged with automatic text resolution. Now: cd apps/desktop && npm install --prefix ../.. && npm run typecheck && npm run test:ui"
