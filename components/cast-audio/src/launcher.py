"""Use the installed, component-owned environment for either Python sidecar."""
import os
from pathlib import Path
import sys

if len(sys.argv) != 2 or sys.argv[1] not in {"main.py", "settings_client.py"}:
    raise SystemExit("Unknown Cast Audio helper")
source = Path(__file__).resolve().parent
python = source.parent / "_venv/bin/python"
interpreter = str(python) if python.is_file() else sys.executable
os.execv(interpreter, [interpreter, "-B", str(source / sys.argv[1])])
