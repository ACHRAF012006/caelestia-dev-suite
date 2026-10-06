import json
import pytest
from backend.paths import SafetyError, relative
from backend.codex.package import parse, encode, detect
from backend.validators import manifest_parse

def test_structured_roundtrip(app_files):
    m, files = app_files
    package = parse(encode(files, m))
    assert package.headers["id"] == m["id"]
    assert set(package.files) == set(files)
    assert manifest_parse(package.files["manifest.json"]) == m

def test_multifile():
    p = parse('--- FILE: src/Main.qml ---\nimport QtQuick\n--- FILE: README.md ---\nHello\n')
    assert p.files == {"src/Main.qml": "import QtQuick\n", "README.md": "Hello\n"}

def test_single_source_is_inert(tmp_path):
    sentinel = tmp_path / "should-never-exist"
    p = parse(f"open({str(sentinel)!r}, 'w').write('bad')")
    assert "src/main.py" in p.files and not sentinel.exists()

@pytest.mark.parametrize("path", ["../../bad", "/etc/passwd", "src/../bad", "~/.local/foo", "src\\foo", "src//foo", "./foo", "foo\nbar", ".git/config", "foo/", "src/./foo"])
def test_bad_paths(path):
    with pytest.raises(SafetyError): relative(path)

@pytest.mark.parametrize("source", ['--- FILE: ../../bad ---\nx', '--- FILE: a ---\nx\n--- FILE: a ---\ny',
    '--- FILE: a ---\nx\n--- FILE: a/b ---\ny', 'CAELESTIA_DEV_PACKAGE\nid: thing', 'explanation\n--- FILE: a ---\nx'])
def test_malicious_packages(source):
    with pytest.raises(SafetyError): parse(source)

def test_conflicting_headers(app_files):
    m, files = app_files
    with pytest.raises(SafetyError): parse(encode(files, m).replace("id: harmless-test", "id: other-test"))

def test_fence(app_files):
    m, files = app_files
    assert parse("```text\n" + encode(files, m) + "\n```").headers["id"] == m["id"]

def test_detection():
    assert detect("from PySide6.QtWidgets import QApplication") == "python-pyside6"
    assert detect("#!/bin/bash\necho hello") == "shell"
    assert detect("import QtQuick") == "qml"
    assert detect("import Quickshell") == "quickshell"

@pytest.mark.parametrize("change", [{"id": "../escape"}, {"id": "caelestia"}, {"runtime": "exec"}, {"version": "latest"},
    {"install_script": "evil.sh"}, {"name": "app\nExec=evil"}, {"entrypoint": "../../main.py"}, {"id": "kbuildsycoca6"},
    {"dependencies": {"python": ["--index-url=http://evil"]}}, {"desktop": {"terminal": "true"}},
    {"desktop": {"categories": "Utility;\nExec=bad"}}, {"service": {"exec": "bad"}}])
def test_manifest_rejection(app_files, change):
    m, _ = app_files
    with pytest.raises(SafetyError): manifest_parse(json.dumps({**m, **change}))

def test_duplicate_json_keys(app_files):
    m, _ = app_files
    raw = json.dumps(m).replace('"id":', '"id": "first", "id":', 1)
    with pytest.raises(SafetyError): manifest_parse(raw)
