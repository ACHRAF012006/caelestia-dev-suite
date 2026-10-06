import json
import subprocess
import shutil
from pathlib import Path
import pytest
from backend.paths import Paths, SafetyError
from backend.manager import Manager
from backend.templates import template

def test_activation_name_is_reserved(manager):
    m, files = template("Plugin", "collision-plugin", "Empty Caelestia Plugin")
    files["metadata.json.disabled"] = "{}"
    with pytest.raises(SafetyError, match="reserved"): manager.create(files)

def test_service_paths_with_spaces_percent_and_dollar(tmp_path):
    if not shutil.which("systemd-analyze"): pytest.skip("systemd verifier unavailable")
    manager = Manager(Paths.sandbox(tmp_path / "space percent% dollar$"), real=False)
    m, files = template("Spaces", "path-service", "systemd User Service")
    manager.create(files)
    plan = manager.plan_install(m["id"])
    for f in plan["files"]:
        f.path.parent.mkdir(parents=True, exist_ok=True); f.path.write_bytes(f.content())
    unit = next(f.path for f in plan["files"] if f.path.suffix == ".service")
    result = subprocess.run(["systemd-analyze", "--user", "verify", str(unit)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
