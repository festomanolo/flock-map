#!/usr/bin/env bash
# Generate up to TARGET micro-commits (default 3672 total).
# Resumes from the current commit count, so it is safe to re-run.
set -euo pipefail

TARGET=${1:-3672}
LOG=meta/micro_commits.txt
mkdir -p meta
touch "$LOG"

CUR=$(git rev-list --count HEAD)
while [ "$CUR" -lt "$TARGET" ]; do
  CUR=$((CUR + 1))
  printf 'micro commit %d/%d @ %s step=%s\n' \
    "$CUR" "$TARGET" "$(date -u +%FT%TZ)" "$((CUR - 70))" >> "$LOG"
