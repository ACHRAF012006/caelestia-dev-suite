#!/bin/bash
set -euo pipefail
TASK_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TASK_REFERENCE="$TASK_PROJECT_ROOT/reference/caelestia-kde"
TASK_UPSTREAM='https://github.com/ladybug-me/caelestia-kde'
if [[ ! -d "$TASK_REFERENCE" ]]; then
    mkdir -p -- "$TASK_PROJECT_ROOT/reference"
    git clone -- "$TASK_UPSTREAM" "$TASK_REFERENCE"
    exit
fi
[[ "$(git -C "$TASK_REFERENCE" remote get-url origin)" == "$TASK_UPSTREAM" || "$(git -C "$TASK_REFERENCE" remote get-url origin)" == "$TASK_UPSTREAM.git" ]] || { echo 'Unexpected reference remote; refused.' >&2; exit 1; }
[[ -z "$(git -C "$TASK_REFERENCE" status --porcelain)" ]] || { echo 'Reference has local changes; refused.' >&2; exit 1; }
[[ "$(git -C "$TASK_REFERENCE" branch --show-current)" == main ]] || { echo 'Reference must be on main; refused.' >&2; exit 1; }
git -C "$TASK_REFERENCE" fetch origin main
git -C "$TASK_REFERENCE" merge --ff-only origin/main
