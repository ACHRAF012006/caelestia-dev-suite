#!/bin/bash
set -euo pipefail
TASK_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
exec python3 "$TASK_PROJECT_ROOT/scripts/install_manager.py" "$TASK_PROJECT_ROOT" "$@"
