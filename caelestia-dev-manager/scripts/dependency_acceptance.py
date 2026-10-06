"""Temporary real isolated-dependency test. No live components are installed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from backend.manager import Manager
from backend.paths import Paths, digest

with tempfile.TemporaryDirectory(prefix="cdm-dependencies-") as directory:
    manager = Manager(Paths.sandbox(directory), real=False)
    m = {"id": "isolated-python-check", "name": "Isolated Python Check", "version": "0.1.0", "description": "Temporary dependency test",
         "type": "standalone-app", "runtime": "python", "entrypoint": "src/main.py", "dependencies": {"python": ["packaging==26.3"]}}
    files = {"manifest.json": json.dumps(m), "src/main.py": "import packaging, sys\nprint(packaging.__version__)\nprint(sys.prefix)\n"}
    manager.create(files); manager.prepare_dependencies(m["id"])
    plan = manager.plan_install(m["id"])
    assert any("_venv/bin/python" in str(f.path) for f in plan["files"])
    manager.install(m["id"], expected=plan)
    result = subprocess.run([str(manager.paths.bin / m["id"])], capture_output=True, text=True, check=True)
    assert "26.3" in result.stdout and str(manager.paths.root(m) / "_venv") in result.stdout
    assert not manager.status(manager.installed(m["id"]))["modified"]
    manager.uninstall(m["id"])
    assert manager.paths.source(m["id"]).exists() and not manager.paths.root(m).exists()
    print("PASS: isolated dependency preparation, exact ownership, installed interpreter relocation, independent launch, unchanged checksums, uninstall/source preservation")
