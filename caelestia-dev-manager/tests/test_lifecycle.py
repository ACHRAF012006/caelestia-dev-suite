import json
from pathlib import Path
import pytest
from backend.paths import SafetyError, digest
from backend.manager import Manager
from backend.templates import template
from backend.installers import installer, FilePlan
from backend.codex import context
from backend.validators import validate
from backend.environment import detect

def create(manager, app_files):
    m, files = app_files
    manager.create(files)
    return m["id"]

def test_registry_persistence(manager, app_files):
    id = create(manager, app_files)
    other = Manager(manager.paths, real=False)
    assert other.registry.get(id)["manifest"]["name"] == "Harmless Test"
    with pytest.raises(SafetyError): manager.create(app_files[1])

def test_install_plan(manager, app_files):
    id = create(manager, app_files); plan = manager.plan_install(id)
    paths = {str(f.path) for f in plan["files"]}
    assert str(manager.paths.bin / id) in paths
    assert str(manager.paths.data / "applications" / (id + ".desktop")) in paths
    assert all(not Path(p).exists() for p in paths)
    assert "exec /" in next(f.content().decode() for f in plan["files"] if f.path == manager.paths.bin / id)

def test_uninstall_only_owned_source_remains(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    record = manager.registry.get(id)
    owned = manager.registry.files(id)
    assert len(owned) == len(app_files[1]) + 2
    extra = manager.paths.root(record["manifest"]) / "user-notes.txt"
    extra.write_text("keep me")
    unrelated = manager.paths.bin / "unrelated"; unrelated.write_text("keep me too")
    assert len(manager.plan_uninstall(id)) == len(owned)
    manager.uninstall(id)
    assert all(not Path(f["path"]).exists() for f in owned)
    assert extra.read_text() == "keep me" and unrelated.read_text() == "keep me too"
    assert manager.paths.source(id).exists() and manager.registry.files(id) == []

def test_ownership_collision(manager, app_files):
    id = create(manager, app_files)
    manager.paths.bin.mkdir(parents=True); (manager.paths.bin / id).write_text("existing command")
    with pytest.raises(SafetyError, match="unowned"): manager.plan_install(id)
    assert (manager.paths.bin / id).read_text() == "existing command"

def test_cross_component_ownership(manager, app_files):
    id = create(manager, app_files)
    manager.registry.db.execute("INSERT INTO ownership VALUES(?,?,?,?)", (str(manager.paths.bin / id), "another-owner", "a", 0o755)); manager.registry.db.commit()
    with pytest.raises(SafetyError, match="Owned by"): manager.plan_install(id)

def test_source_vs_installed(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    installed = manager.paths.root(app_files[0]) / "src/main.py"; original = installed.read_text()
    manager.save_file(id, "src/main.py", 'print("updated")\n')
    assert manager.status(manager.registry.get(id))["source_modified"]
    assert installed.read_text() == original
    manager.install(id)
    assert installed.read_text() == 'print("updated")\n'
    assert not manager.status(manager.registry.get(id))["source_modified"]

def test_stale_plan_rejected(manager, app_files):
    id = create(manager, app_files); plan = manager.plan_install(id)
    manager.save_file(id, "src/main.py", 'print("new")\n')
    with pytest.raises(SafetyError, match="since preview"): manager.install(id, expected=plan)
    assert manager.registry.files(id) == []

def test_modified_installed_file_preserved(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    target = manager.paths.root(app_files[0]) / "src/main.py"; target.write_text("user edits")
    assert manager.status(manager.registry.get(id))["modified"]
    with pytest.raises(SafetyError): manager.uninstall(id)
    with pytest.raises(SafetyError): manager.install(id)
    assert target.read_text() == "user edits"
    backup = manager.backup(id)
    assert any(f.get("checksum") == digest(b"user edits") for f in backup["files"])

def test_missing_status_repair(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    (manager.paths.bin / id).unlink()
    assert manager.status(manager.registry.get(id))["status"] == "Missing Files"
    manager.install(id)
    assert (manager.paths.bin / id).exists()

def test_enable_disable(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    desktop = manager.paths.data / "applications" / (id + ".desktop")
    manager.set_enabled(id, False)
    assert "Hidden=true" in desktop.read_text()
    assert (manager.paths.bin / id).stat().st_mode & 0o111 == 0
    manager.set_enabled(id, True)
    assert "Hidden=false" in desktop.read_text()
    assert (manager.paths.bin / id).stat().st_mode & 0o111
    manager.uninstall(id)

def test_update_stays_disabled(manager, app_files):
    id = create(manager, app_files); manager.install(id); manager.set_enabled(id, False)
    manager.save_file(id, "src/main.py", 'print("changed")\n'); manager.install(id)
    assert not manager.registry.get(id)["enabled"]
    assert not (manager.paths.bin / id).stat().st_mode & 0o111

def test_backup_restore_and_metadata(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    old_hash = manager.registry.get(id)["installed_source_hash"]
    meta = manager.backup(id)
    assert {"component_id", "version", "date", "manager_version", "files"}.issubset(meta)
    assert all("path" in f and "checksum" in f for f in meta["files"])
    manager.save_file(id, "src/main.py", 'print("changed")\n'); manager.install(id)
    manager.restore(meta["backup_id"])
    assert (manager.paths.root(app_files[0]) / "src/main.py").read_text() == app_files[1]["src/main.py"]
    assert manager.registry.get(id)["installed_source_hash"] == old_hash
    assert manager.status(manager.registry.get(id))["source_modified"]

def test_backup_checksum_tampering(manager, app_files):
    id = create(manager, app_files); manager.install(id); b = manager.backup(id)
    (manager.paths.backups / b["backup_id"] / "0").write_bytes(b"corrupt")
    with pytest.raises(SafetyError, match="checksum"): manager.backups.read(b["backup_id"])

def test_update_automatic_backup_restores_old_manifest(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    m = {**app_files[0], "version": "0.2.0"}
    manager.save_file(id, "manifest.json", json.dumps(m)); manager.install(id)
    backup = next(b for b in manager.backups.list() if b["reason"] == "Updated installed version")
    manager.restore(backup["backup_id"])
    assert manager.registry.get(id)["installed_manifest"]["version"] == "0.1.0"

def test_restore_after_uninstall(manager, app_files):
    id = create(manager, app_files); manager.install(id); manager.uninstall(id)
    b = next(b for b in manager.backups.list() if b["reason"].startswith("Uninstalled"))
    manager.restore(b["backup_id"])
    assert manager.registry.get(id)["installed"] and (manager.paths.bin / id).exists()

def test_service_plan_lifecycle(manager):
    m, files = template("Test Service", "test-service", "systemd User Service")
    manager.create(files); plan = manager.plan_install(m["id"])
    unit = next(f for f in plan["files"] if f.path.suffix == ".service")
    text = unit.content().decode()
    assert "WantedBy=default.target" in text and "ExecStart=" in text and "app.main" not in text
    manager.install(m["id"])
    assert not manager.registry.get(m["id"])["enabled"]
    manager.runtime.launch(manager.installed(m["id"]))
    assert ["start", "cdm-test-service.service"] in manager.runtime.calls
    manager.set_enabled(m["id"], True); manager.set_enabled(m["id"], False); manager.uninstall(m["id"])
    assert ["enable", "--now", "cdm-test-service.service"] in manager.runtime.calls
    assert ["disable", "--now", "cdm-test-service.service"] in manager.runtime.calls

def test_service_unit_accepted_by_systemd(manager):
    import shutil
    import subprocess
    if not shutil.which("systemd-analyze"): pytest.skip("systemd-analyze unavailable")
    # Generated unit verification is read-only and uses only temporary files.
    m, files = template("Quoted service", "quoted-service", "systemd User Service")
    m["args"] = ["literal $HOME", "percent%value", 'quoted"arg']
    files["manifest.json"] = json.dumps(m)
    manager.create(files)
    plan = manager.plan_install(m["id"])
    root = manager.paths.root(m); root.mkdir(parents=True)
    for f in plan["files"]:
        f.path.parent.mkdir(parents=True, exist_ok=True); f.path.write_bytes(f.content())
    unit = next(f.path for f in plan["files"] if f.path.suffix == ".service")
    result = subprocess.run(["systemd-analyze", "--user", "verify", str(unit)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_crash_recovery_requires_explicit_action(manager, app_files, monkeypatch):
    id = create(manager, app_files); manager.install(id)
    original_files = [(f["path"], Path(f["path"]).read_bytes()) for f in manager.registry.files(id)]
    manager.save_file(id, "README.md", "New source readme")
    original = FilePlan.content; calls = []
    def crash(self):
        if manager.journal.exists():
            calls.append(self.path)
            if len(calls) == 2: raise SystemExit("Simulated process crash")
        return original(self)
    monkeypatch.setattr(FilePlan, "content", crash)
    with pytest.raises(SystemExit): manager.install(id)
    assert manager.journal.exists()
    reopened = Manager(manager.paths, real=False)
    with pytest.raises(SafetyError, match="needs recovery"): reopened.plan_install(id)
    assert "recovered" in reopened.recover()
    assert not manager.journal.exists()
    assert all(Path(p).read_bytes() == data for p, data in original_files)

def test_unowned_directory_is_not_adopted(manager, app_files):
    id = create(manager, app_files)
    root = manager.paths.root(app_files[0]); root.mkdir(parents=True); (root / "other.txt").write_text("keep")
    with pytest.raises(SafetyError, match="unowned component directory"): manager.plan_install(id)

def test_schema_and_permission_change_rejected(manager, app_files):
    from backend.validators import manifest_parse
    m, _ = app_files
    with pytest.raises(SafetyError): manifest_parse(json.dumps({**m, "schema_version": 3}))
    id = create(manager, app_files); manager.install(id)
    target = manager.paths.bin / id; target.chmod(0o600)
    with pytest.raises(SafetyError): manager.uninstall(id)

def test_installed_compatibility_tracks_environment(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    record = manager.registry.get(id)
    record["installed_manifest"]["compatibility"] = {"plasma": "impossible-version"}
    assert manager.status(record)["status"] == "Incompatible"

def test_missing_executable_is_identified_without_allowing_install(manager, app_files, monkeypatch):
    import shutil
    original_which = shutil.which
    m, files = app_files
    m["dependencies"] = {"system": ["catt"], "python": []}
    files["manifest.json"] = json.dumps(m)
    monkeypatch.setattr("backend.validators.shutil.which", lambda name: "/test/catt" if name == "catt" else original_which(name))
    manager.create(files)
    monkeypatch.setattr("backend.validators.shutil.which", lambda name: None if name == "catt" else original_which(name))
    status = manager.status(manager.registry.get(m["id"]))
    assert status["status"] == "Missing Dependencies"
    assert status["compatible"]
    assert status["validation"]["errors"] == ["Missing system executable: catt (install manually)"]
    with pytest.raises(SafetyError, match="Missing system executable: catt"):
        manager.plan_install(m["id"])
    # An actual source error still takes precedence over the dependency label.
    manager.save_file(m["id"], "src/main.py", "def broken(")
    assert manager.status(manager.registry.get(m["id"]))["status"] == "Incompatible / Broken"
    assert not manager.registry.files(m["id"])

def fake_shell(manager):
    from backend.paths import atomic_write
    atomic_write(manager.paths.shell / "services/PluginLoader.qml", b'metadata.json Qt.createComponent target: "plugins"')
    atomic_write(manager.paths.shell / "scripts/list-plugins.sh", b'/caelestia/plugins')

def test_caelestia_plan_lifecycle(manager):
    fake_shell(manager)
    m, files = template("Test Plugin", "test-plugin", "Empty Caelestia Plugin")
    manager.create(files); plan = manager.plan_install(m["id"])
    assert all(str(f.path).startswith(str(manager.paths.config / "caelestia/plugins/test-plugin")) for f in plan["files"])
    assert any(f.path.name == "metadata.json.disabled" for f in plan["files"])
    assert not any(f.path.name == "metadata.json" for f in plan["files"])
    manager.install(m["id"], expected=plan)
    assert not (manager.paths.root(m) / "metadata.json").exists()
    manager.set_enabled(m["id"], True)
    assert (manager.paths.root(m) / "metadata.json").exists()
    manager.set_enabled(m["id"], False)
    assert not (manager.paths.root(m) / "metadata.json").exists()
    manager.install(m["id"])
    assert not (manager.paths.root(m) / "metadata.json").exists()
    manager.uninstall(m["id"])
    assert manager.paths.source(m["id"]).exists()

def test_unverified_caelestia_fails_closed(manager):
    m, files = template("Test Plugin", "test-plugin", "Empty Caelestia Plugin")
    manager.create(files)
    with pytest.raises(SafetyError, match="could not be verified"): manager.plan_install(m["id"])

def test_environment_detection_no_writes(manager):
    before = list(manager.paths.config.rglob("*"))
    env = detect(manager.paths)
    assert {"os", "session", "plasma_version", "plugin_supported", "caelestia_commit"}.issubset(env)
    assert list(manager.paths.config.rglob("*")) == before

def test_context(manager, app_files):
    id = create(manager, app_files)
    prompt = context(manager, "Build a widget")
    for text in ("CAELESTIA_DEV_PACKAGE", "PROJECT_CONTEXT.md", "docs/PLUGIN_SPEC.md", "must not require Dev Manager", "Build a widget", id): assert text in prompt

def test_symlink_rejected(manager, app_files, tmp_path):
    id = create(manager, app_files)
    outside = tmp_path / "outside.py"; outside.write_text("keep me")
    link = manager.paths.source(id) / "src/escape.py"; link.symlink_to(outside)
    with pytest.raises(SafetyError): manager.read_source(id)
    with pytest.raises(SafetyError): manager.delete_source(id, id)
    assert outside.read_text() == "keep me"

def test_destination_parent_symlink_rejected(manager, app_files, tmp_path):
    id = create(manager, app_files)
    outside = tmp_path / "outside"; outside.mkdir()
    manager.paths.bin.symlink_to(outside)
    with pytest.raises(SafetyError): manager.plan_install(id)
    assert not list(outside.iterdir())

def test_delete_source_separate_and_confirmed(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    with pytest.raises(SafetyError): manager.delete_source(id, "yes")
    manager.delete_source(id, id)
    assert not manager.paths.source(id).exists()
    assert (manager.paths.bin / id).exists()
    assert not manager.status(manager.registry.get(id))["source_exists"]
    manager.uninstall(id)

def test_install_failure_rolls_back(manager, app_files, monkeypatch):
    id = create(manager, app_files); manager.install(id)
    old = [(f["path"], Path(f["path"]).read_bytes()) for f in manager.registry.files(id)]
    manager.save_file(id, "src/main.py", 'print("new version")\n')
    original = FilePlan.content
    calls = []
    def failure(self):
        if manager.journal.exists():
            calls.append(self.path)
            if len(calls) == 2: raise OSError("Simulated write failure")
        return original(self)
    monkeypatch.setattr(FilePlan, "content", failure)
    with pytest.raises(OSError): manager.install(id)
    assert not manager.journal.exists()
    assert all(Path(p).read_bytes() == data for p, data in old)

def test_removing_source_file_updates_ownership(manager, app_files):
    id = create(manager, app_files); manager.install(id)
    manager.remove_file(id, "README.md"); manager.install(id)
    assert not (manager.paths.root(app_files[0]) / "README.md").exists()
    assert not any(f["path"].endswith("README.md") for f in manager.registry.files(id))

def test_reserved_venv_source(manager, app_files):
    _, files = app_files
    files["_venv/bin/python"] = "evil"
    with pytest.raises(SafetyError): manager.create(files)

def test_static_python_errors(manager, app_files):
    _, files = app_files; files["src/main.py"] = "def broken("
    with pytest.raises(SafetyError): manager.create(files)
    manager.create(files, draft=True)
    assert manager.registry.get("harmless-test")["draft"]

def test_no_arbitrary_install_hook(manager, app_files, tmp_path):
    m, files = app_files; files["install.sh"] = "#!/bin/bash\ntouch /tmp/must-not-run\n"
    manager.create(files)
    assert any("inert" in x for x in manager.validation(m["id"])["warnings"])
    manager.install(m["id"])

def test_dependency_plan_needs_preparation(manager):
    m, files = template("GUI", "gui-test", "Python + PySide6 Application")
    manager.create(files)
    with pytest.raises(SafetyError, match="Prepare Python dependencies"): manager.plan_install(m["id"])

def test_qml_target_and_reserved_kde(manager):
    m, files = template("QML", "qml-test", "QML Component")
    assert validate(files, m)["valid"]
    m.pop("integration")
    assert not validate(files, m)["valid"]
    m["type"] = "kde-integration"
    assert not validate(files, m)["valid"]
