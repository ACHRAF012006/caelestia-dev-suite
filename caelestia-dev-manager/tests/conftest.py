import json
import pytest
from backend.paths import Paths
from backend.manager import Manager
from backend.templates import template

@pytest.fixture
def manager(tmp_path): return Manager(Paths.sandbox(tmp_path), real=False)

@pytest.fixture
def app_files():
    m, files = template("Harmless Test", "harmless-test", "Python Script", "Test-only command")
    m["type"] = "standalone-app"
    files["manifest.json"] = json.dumps(m)
    return m, files
