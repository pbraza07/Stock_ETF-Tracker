#!/usr/bin/env bash
set -euo pipefail

# MarketScope v5.9.55
# Persist generated data to main without losing it when another commit lands
# while the long refresh job is running.
#
# Usage:
#   scripts/persist_generated_files.sh "commit message" file1 file2 ...

if [[ "$#" -lt 2 ]]; then
  echo "Usage: $0 <commit-message> <file> [file ...]" >&2
  exit 2
fi

COMMIT_MESSAGE="$1"
shift
FILES=("$@")
MAX_ATTEMPTS="${MARKETSCOPE_GIT_PUSH_ATTEMPTS:-6}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

TEMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Save the generated outputs outside the worktree before any fetch/reset.
for file in "${FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Required generated file is missing: $file" >&2
    exit 3
  fi
  mkdir -p "$TEMP_DIR/$(dirname "$file")"
  cp -p "$file" "$TEMP_DIR/$file"
done

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "Persistence attempt ${attempt}/${MAX_ATTEMPTS}"

  # Always start from the newest remote main. This intentionally discards the
  # prior failed local data commit while the generated files remain protected
  # in TEMP_DIR.
  git fetch --no-tags origin main
  git reset --hard origin/main

  # Restore only the generated MarketScope files on top of the newest code.
  for file in "${FILES[@]}"; do
    mkdir -p "$(dirname "$file")"
    cp -p "$TEMP_DIR/$file" "$file"
  done

  git add -- "${FILES[@]}"

  if git diff --cached --quiet; then
    echo "Generated data already matches origin/main; nothing to push."
    exit 0
  fi

  git commit -m "$COMMIT_MESSAGE"

  # A concurrent commit may still arrive in the tiny interval between fetch
  # and push. If that happens, loop, fetch the new main, restore the exact
  # generated files again, create a fresh commit, and retry.
  if git push origin HEAD:main; then
    echo "Generated MarketScope data persisted successfully."
    exit 0
  fi

  echo "Push was rejected because main changed concurrently. Retrying safely..."
  sleep $((attempt * 2))
done

echo "Unable to persist generated MarketScope data after ${MAX_ATTEMPTS} attempts." >&2
exit 4
