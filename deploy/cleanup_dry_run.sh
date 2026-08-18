#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="${SOAIA_DATA_ROOT:-/var/lib/soaia}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf 'SOAIA_CLEANUP_DRY_RUN_V1\n'
printf 'timestamp_utc=%s\n' "$NOW"
printf 'root=%s\n' "$ROOT"

[[ -d "$ROOT" ]] || { echo "WARN data root absent; nothing to inspect"; exit 0; }

find "$ROOT" -type f -print0 | while IFS= read -r -d '' f; do
  case "$f" in
    */backup-staging/*|*/tmp/*|*/cache/*)
      age_days=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 86400 ))
      sha=$(sha256sum "$f" | awk '{print $1}')
      size=$(stat -c %s "$f")
      printf 'candidate\t%s\t%s\t%s\t%s\n' "$age_days" "$size" "$sha" "$f"
      ;;
  esac
done

printf 'MODE=DRY_RUN_ONLY\n'
printf 'No files were deleted. Destructive cleanup requires explicit retention classification and approval gate.\n'
