import json
import os
import subprocess
import copy
from unittest.mock import patch

import pytest

from backend.dependencies import DependencyError, clean_output, failure_report, report
from backend.paths import SafetyError
from backend.templates import template


def component(manager, id="dependency-test", deps=None):
    m, files = template("Dependency Test", id, "Python Script")
    m["dependencies"] = {"python": deps or ["demo>=2"], "system": []}
    files["manifest.json"] = json.dumps(m)
    manager.create(files)
    return m


def metadata(environment, name, version):
    folder = environment / "lib/python3.14/site-packages" / (name + "-" + version + ".dist-info")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "METADATA").write_text("Metadata-Version: 2.1\nName: " + name + "\nVersion: " + version + "\n")


def test_component_reports_own_environment_and_version(manager, monkeypatch):
    m = component(manager)
    component(manager, "other-dependency")
    target = manager.prepared_path(m)
    before = manager.dependency_status(m["id"])["development"]
    assert before["python"][0]["status"] == "not prepared"
    metadata(target, "demo", "1.0")
    (target / "pyvenv.cfg").write_text("version = 3.13.7\n")
    assert manager.dependency_status(m["id"])["development"]["python_version"] == "3.13.7"
    assert manager.dependency_status(m["id"])["development"]["python"][0]["status"] == "version mismatch"
    assert manager.dependency_status("other-dependency")["development"]["python"][0]["status"] == "not prepared"
    # Never import a component package or execute its interpreter during inspection.
    site = target / "lib/python3.14/site-packages"
    (site / "demo.py").write_text("raise RuntimeError('must not import')")
    with patch("backend.dependencies.shutil.which", return_value=None):
        m["dependencies"]["system"] = ["missing-tool"]
        result = report(m, target)
        assert result["system"][0]["status"] == "missing"
        assert not result["ready"]


def test_failure_names_transitive_package_and_redacts_index(manager, monkeypatch):
    m = component(manager, deps=["PySide6>=6.8", "pulsectl>=24.4.0"])
    target = manager.prepared_path(m)
    def run(command, **kwargs):
        assert kwargs["capture_output"] and kwargs["text"]
        if "venv" in command:
            (target / "bin").mkdir(parents=True)
            (target / "bin/python").write_text("fake interpreter")
            return subprocess.CompletedProcess(command, 0)
        assert "--only-binary=:all:" in command
        assert kwargs["env"]["PIP_REQUIRE_VIRTUALENV"] == "true"
        raise subprocess.CalledProcessError(1, command, output="Looking in indexes: https://user:secret@example.test/simple?token=hidden\n",
                                            stderr="ERROR: Could not find a version that satisfies the requirement PySide6-Essentials==6.8.1 (from versions: none)\nERROR: No matching distribution found for PySide6-Essentials==6.8.1")
    monkeypatch.setattr("backend.manager.subprocess.run", run)
    with pytest.raises(DependencyError) as raised:
        manager.prepare_dependencies(m["id"])
    error = raised.value
    assert error.report["reported_requirements"] == ["PySide6-Essentials==6.8.1"]
    assert "PySide6-Essentials" in str(error)
    assert "Captured output" in error.details()
    assert not (target.parent / "prepared.json").exists()
    stored = (target.parent / "dependency-error.json").read_text()
    assert "secret" not in stored and "hidden" not in stored
    assert "secret" not in "\n".join(manager.registry.logs())
    assert manager.dependency_status(m["id"])["development"]["last_preparation_error"]["stage"] == "packages"
    assert not manager.registry.get(m["id"])["installed"]


def test_network_error_is_not_reported_as_confirmed_missing_package():
    m = {"id": "net-test", "name": "Network Test", "dependencies": {"python": ["demo"]}}
    error = subprocess.CalledProcessError(1, ["pip"], stderr="WARNING: Connection broken by 'ReadTimeoutError'\nERROR: No matching distribution found for demo")
    data = failure_report(m, "packages", error)
    assert "Network" in data["reason"]
    assert "does not establish" in data["reason"]
    timeout = failure_report(m, "packages", subprocess.TimeoutExpired(["pip"], 600, output=b"progress", stderr=b"timeout"))
    assert "timed out" in timeout["reason"] and "progress" in timeout["output"]


def test_retry_clears_error_only_after_successful_verified_preparation(manager, monkeypatch):
    m = component(manager)
    target = manager.prepared_path(m)
    target.parent.mkdir(parents=True)
    (target.parent / "dependency-error.json").write_text('{"reason":"old failure"}')
    attempts = []
    def run(command, **kwargs):
        attempts.append(command)
        if "venv" in command:
            (target / "bin").mkdir(parents=True, exist_ok=True)
            (target / "bin/python").write_text("fake interpreter")
        else:
            metadata(target, "demo", "2.1")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("backend.manager.subprocess.run", run)
    assert manager.prepare_dependencies(m["id"]) == str(target)
    assert manager.dependencies_prepared(m)
    assert not (target.parent / "dependency-error.json").exists()
    assert manager.dependency_status(m["id"])["development"]["ready"]
    assert manager.prepare_dependencies(m["id"]) == str(target)
    assert len(attempts) == 2
    # A marker alone cannot hide missing installed distribution metadata.
    info = next(target.glob("lib/python*/site-packages/*.dist-info/METADATA"))
    info.unlink()
    assert not manager.dependencies_prepared(m)


def test_creation_failure_and_success_with_missing_metadata_are_diagnostic(manager, monkeypatch):
    m = component(manager)
    def missing_python(*args, **kwargs): raise FileNotFoundError("python3 unavailable")
    monkeypatch.setattr("backend.manager.subprocess.run", missing_python)
    with pytest.raises(DependencyError) as raised: manager.prepare_dependencies(m["id"])
    assert raised.value.report["stage"] == "environment"
    monkeypatch.setattr("backend.manager.subprocess.run", lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
    with pytest.raises(DependencyError) as raised: manager.prepare_dependencies(m["id"])
    assert raised.value.report["stage"] == "verification"
    assert "demo>=2" in raised.value.report["output"]


def test_metadata_symlinks_are_refused_and_invalid_requirements_are_visible(manager):
    m = component(manager)
    target = manager.prepared_path(m)
    metadata(target, "demo", "2")
    info = next(target.glob("lib/python*/site-packages/*.dist-info/METADATA"))
    info.unlink()
    info.symlink_to(manager.paths.source(m["id"]) / "manifest.json")
    result = manager.dependency_status(m["id"])["development"]
    assert not result["ready"] and "symlink" in result["inspection_error"].lower()
    m["dependencies"]["python"] = ["demo~2"]
    assert report(m, target)["python"][0]["status"] == "invalid requirement"


def test_dependency_ui_and_failure_dialog(manager, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.main import Window
    app = QApplication.instance() or QApplication([])
    m = component(manager)
    window = Window(manager)
    window.select_id(m["id"])
    assert window.actions["dependencies"].isEnabled()
    assert "demo>=2 (not prepared)" in window.dependency_state.text()
    dialogs = []
    monkeypatch.setattr(window, "show_text", lambda title, text: dialogs.append((title, text)))
    window.show_dependencies()
    assert "installed version: none" in dialogs[-1][1]
    def fail():
        raise DependencyError(failure_report(m, "packages", subprocess.CalledProcessError(1, ["pip"], stderr="ERROR: No matching distribution found for demo>=2")))
    assert window.guard(fail) is None
    assert dialogs[-1][0] == "Dependency preparation failed"
    assert "demo>=2" in dialogs[-1][1]
    window.close()
    app.processEvents()


def test_installed_manifest_is_checked_independently_and_broken_source_is_safe(manager):
    m = component(manager)
    installed = copy.deepcopy(m)
    installed["dependencies"]["python"] = ["demo==1"]
    record = manager.registry.get(m["id"])
    record.update(installed=True, installed_manifest=installed)
    with manager.registry.db: manager.registry.save(record)
    metadata(manager.paths.root(installed) / "_venv", "demo", "1")
    result = manager.dependency_status(m["id"])
    assert result["installed"]["ready"]
    assert result["installed"]["python"][0]["installed_version"] == "1"
    assert result["development"]["python"][0]["status"] == "not prepared"
    (manager.paths.source(m["id"]) / "manifest.json").write_text("{broken")
    result = manager.dependency_status(m["id"])
    assert result["source_manifest_error"]
    assert result["development"]["python"][0]["requirement"] == "demo>=2"


def test_failed_preparation_is_retained_after_reopen_and_venv_link_retry(manager, monkeypatch):
    from backend.manager import Manager
    m = component(manager)
    target = manager.prepared_path(m)
    first = [True]
    def run(command, **kwargs):
        if "venv" in command:
            (target / "bin").mkdir(parents=True, exist_ok=True)
            (target / "bin/python").write_text("fake interpreter")
            (target / "lib").mkdir(exist_ok=True)
            (target / "lib64").symlink_to("lib")
            if first[0]:
                first[0] = False
                raise subprocess.CalledProcessError(1, command, stderr="ensurepip failed")
        else:
            metadata(target, "demo", "2")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("backend.manager.subprocess.run", run)
    with pytest.raises(DependencyError): manager.prepare_dependencies(m["id"])
    reopened = Manager(manager.paths, real=False)
    assert reopened.dependency_status(m["id"])["development"]["last_preparation_error"]["stage"] == "environment"
    manager.prepare_dependencies(m["id"])
    assert not (target / "lib64").is_symlink()
    assert reopened.dependency_status(m["id"])["development"]["ready"]


def test_quickshell_sidecar_dependencies_are_installed_owned_and_independent(manager, monkeypatch):
    environment = {"plugin_supported": True}
    monkeypatch.setattr("backend.manager.detect", lambda paths: environment)
    manager.environment = environment
    m, files = template("Helper Plugin", "helper-plugin", "Empty Caelestia Plugin")
    m["dependencies"] = {"python": ["demo>=2"], "system": []}
    files["manifest.json"] = json.dumps(m)
    manager.create(files)
    target = manager.prepared_path(m)
    def run(command, **kwargs):
        if "venv" in command:
            (target / "bin").mkdir(parents=True)
            (target / "bin/python").write_text("private interpreter")
        else:
            metadata(target, "demo", "2")
            (target / "lib/python3.14/site-packages/demo.py").write_text("value = 2\n")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr("backend.manager.subprocess.run", run)
    with pytest.raises(SafetyError, match="Prepare Python dependencies"):
        manager.plan_install(m["id"])
    manager.prepare_dependencies(m["id"])
    plan = manager.plan_install(m["id"])
    manager.install(m["id"], expected=plan)
    root = manager.paths.root(m)
    assert (root / "_venv/bin/python").is_file()
    assert manager.dependency_status(m["id"])["installed"]["ready"]
    assert str(root / "_venv/bin/python") in {f["path"] for f in manager.registry.files(m["id"])}
    # Runtime libraries belong to the installed snapshot, not staging or manager.
    (target / "lib/python3.14/site-packages/demo.py").unlink()
    assert (root / "_venv/lib/python3.14/site-packages/demo.py").read_text() == "value = 2\n"
    manager.uninstall(m["id"])
    assert not (root / "_venv/bin/python").exists()
