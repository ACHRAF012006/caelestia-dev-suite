"""Install/update/uninstall the manager in a temporary HOME and verify app survival."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

project = Path(__file__).resolve().parents[1]
version_expected = tomllib.loads((project / "pyproject.toml").read_text())["project"]["version"]
with tempfile.TemporaryDirectory(prefix="cdm-manager-install-") as directory:
    root = Path(directory)
    env = {**os.environ, "HOME": str(root / "home"), "XDG_DATA_HOME": str(root / "data"),
           "XDG_CONFIG_HOME": str(root / "config"), "XDG_STATE_HOME": str(root / "state"),
           "XDG_CACHE_HOME": str(root / "cache"), "PIP_CACHE_DIR": str(Path.home() / ".cache/pip"),
           "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen"}
    subprocess.run([str(project / "install.sh")], env=env, check=True, stdout=subprocess.DEVNULL)
    installed_python = root / "data/caelestia-dev-manager/manager/venv/bin/python"
    # Untrusted component code in the current directory cannot shadow the installed manager module.
    shadow = root / "untrusted-cwd/app"; shadow.mkdir(parents=True)
    (shadow / "__init__.py").write_text("")
    sentinel = root / "shadow-executed"
    (shadow / "main.py").write_text(f"open({str(sentinel)!r}, 'w').write('bad')\n")
    version = subprocess.run([str(root / "home/.local/bin/caelestia-dev-manager"), "--version"], env=env, cwd=shadow.parent, capture_output=True, text=True, check=True)
    assert version.stdout.strip() == version_expected and not sentinel.exists()
    icon = root / "data/caelestia-dev-manager/manager/icon.svg"
    desktop = root / "data/applications/caelestia-dev-manager.desktop"
    assert icon.read_bytes() == (project / "app/assets/icon.svg").read_bytes()
    assert f"Icon={icon}\n" in desktop.read_text()
    receipt = json.loads((root / "config/caelestia-dev-manager/manager-install.json").read_text())
    assert str(icon) in {f["path"] for f in receipt["files"]}
    setup = '''
import json, sys
from pathlib import Path
from backend.paths import Paths
from backend.manager import Manager
m = Manager(Paths.default(Path(sys.argv[1])), real=False)
manifest = {"id":"uninstall-survivor","name":"Uninstall Survivor","version":"0.1.0","type":"standalone-app","runtime":"python","entrypoint":"src/main.py"}
m.create({"manifest.json":json.dumps(manifest),"src/main.py":"print('independent-survivor')\\n"})
m.install(manifest["id"])
'''
    subprocess.run([str(installed_python), "-c", setup, str(root / "development")], env=env, check=True, stdout=subprocess.DEVNULL)
    # Updating the manager must preserve component files and its separate database.
    subprocess.run([str(project / "install.sh")], env=env, check=True, stdout=subprocess.DEVNULL)
    database = root / "state/caelestia-dev-manager/registry.sqlite3"
    source = root / "development/plugins/uninstall-survivor/src/main.py"
    before_database = database.read_bytes(); before_source = source.read_bytes()
    subprocess.run([str(project / "uninstall.sh")], env=env, check=True, stdout=subprocess.DEVNULL)
    assert database.read_bytes() == before_database and source.read_bytes() == before_source
    assert not (root / "home/.local/bin/caelestia-dev-manager").exists()
    assert not (root / "data/applications/caelestia-dev-manager.desktop").exists()
    assert not icon.exists()
    result = subprocess.run([str(root / "home/.local/bin/uninstall-survivor")], env=env, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "independent-survivor"
    assert (root / "data/applications/uninstall-survivor.desktop").exists()
    print("PASS: manager install/update/uninstall preserved registry/source/component app and independent launch")
