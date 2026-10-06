#!/bin/bash
set -euo pipefail
TASK_PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$TASK_PROJECT_ROOT/scripts/install_manager.py" "$TASK_PROJECT_ROOT" --uninstall "$@"
