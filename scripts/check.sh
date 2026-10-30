#!/usr/bin/env bash
# Check tracked and untracked files; an optional argument selects one hook.
set -euo pipefail

if (( $# > 1 )) || { (( $# == 1 )) && [[ ! $1 =~ ^[a-z][a-z0-9-]*$ ]]; }; then
  printf 'Usage: bash scripts/check.sh [hook-id]\n' >&2
  exit 2
fi

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd -- "$project_root"

# Native Windows tools need Windows-style environment paths under Git Bash.
native_root=$project_root
if command -v cygpath >/dev/null 2>&1; then
  native_root=$(cygpath -m "$project_root")
fi
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$native_root/.cache/pre-commit}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$native_root/.cache/uv}"
export npm_config_cache="${npm_config_cache:-$native_root/.cache/npm}"

# A temporary NUL-delimited list preserves names and exposes Git failures.
mkdir -p -- "$project_root/.cache"
file_list=$(mktemp "$project_root/.cache/check-files.XXXXXX")
trap 'rm -f -- "$file_list"' EXIT
git ls-files --cached --others --exclude-standard -z > "$file_list"
files=()
while IFS= read -r -d '' filename; do
  files+=("$filename")
done < "$file_list"

check_arguments=(run)
if (( $# == 1 )); then
  check_arguments+=("$1")
fi
check_arguments+=(--files "${files[@]}")
pre-commit "${check_arguments[@]}"
