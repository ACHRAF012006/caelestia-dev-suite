import json
import shutil
import subprocess
from pathlib import Path
import pytest
from backend.desktop import desktop_directory, shortcut_filename, ShortcutConflict
from backend.manager import Manager
from backend.paths import SafetyError, atomic_write
from backend.templates import template
from backend.validators import manifest_parse
from backend.codex import context

def configure(manager, value='$HOME/Bureau personnalisé'):
    atomic_write(manager.paths.config / "user-dirs.dirs", ('XDG_DESKTOP_DIR="' + value + '"\n').encode())
    return desktop_directory(manager.paths)

def create_app(manager, app_files, shortcut=False):
    m, files = app_files
    if shortcut: m["desktop"] = {"createShortcut": True, "startupNotify": True, "terminal": False, "categories": "Utility;"}
    files["manifest.json"] = json.dumps(m)
    manager.create(files)
    return m

def test_xdg_localized_home_expansion(manager):
    assert configure(manager) == manager.paths.home / "Bureau personnalisé"
    assert configure(manager, '${HOME}/Custom Desktop') == manager.paths.home / "Custom Desktop"

def test_xdg_custom_absolute_directory(manager, tmp_path):
    custom = tmp_path / "custom location"
    assert configure(manager, str(custom)) == custom

def test_unset_and_disabled_directory(manager):
    assert desktop_directory(manager.paths) is None
    assert configure(manager, '$HOME/') is None
    assert configure(manager, '') is None

@pytest.mark.parametrize("value", ["../../escape", "/tmp/../etc", "$(touch /tmp/never-run)", "$OTHER/Bureau", "`touch /tmp/never-run`", "/etc", "/usr/share/Desktop", "/"])
def test_xdg_rejects_unsafe_configuration(manager, value):
    with pytest.raises(SafetyError): configure(manager, value)

def test_configuration_is_not_executed(manager, tmp_path):
    sentinel = tmp_path / "must-not-exist"
    with pytest.raises(SafetyError): configure(manager, f'$(touch {sentinel})')
    assert not sentinel.exists()

def test_xdg_symlink_directory_rejected(manager, tmp_path):
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "link"; link.symlink_to(real, target_is_directory=True)
    with pytest.raises(SafetyError): configure(manager, str(link))

def test_shortcut_is_off_by_default(manager, app_files):
    m = create_app(manager, app_files)
    plan = manager.plan_install(m["id"])
    assert plan["desktop_shortcut"] is None and not plan["create_shortcut"]
    manager.install(m["id"], expected=plan)
    assert not manager.has_desktop_shortcut(m["id"])
    assert manager.canonical_desktop(m).is_file()

def test_manifest_shortcut_install_and_ownership(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files, True)
    plan = manager.plan_install(m["id"]); target = directory / (m["name"] + ".desktop")
    assert any(f.path == target for f in plan["files"]) and not target.exists()
    manager.install(m["id"], expected=plan)
    assert target.read_bytes() == manager.canonical_desktop(m).read_bytes()
    assert "StartupNotify=true" in target.read_text()
    assert target.stat().st_mode & 0o777 == 0o755
    assert manager.registry.owner(target) == m["id"]
    assert manager.has_desktop_shortcut(m["id"])
    reopened = Manager(manager.paths, real=False)
    assert reopened.has_desktop_shortcut(m["id"])
    assert reopened.status(reopened.installed(m["id"]))["desktop_shortcut_state"] == "Created"

def test_toggle_without_reinstalling_payload(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    payload = manager.paths.root(m) / "src/main.py"; before = payload.stat().st_mtime_ns
    source = manager.paths.source(m["id"]) / "manifest.json"; source_before = source.read_bytes()
    installed_hash = manager.installed(m["id"])["installed_source_hash"]
    target = manager.create_desktop_shortcut(m["id"])
    assert payload.stat().st_mtime_ns == before
    assert source.read_bytes() == source_before
    assert manager.installed(m["id"])["installed_source_hash"] == installed_hash
    manager.remove_desktop_shortcut(m["id"])
    assert not target.exists() and manager.registry.owner(target) is None
    assert payload.stat().st_mtime_ns == before and manager.canonical_desktop(m).is_file()
    assert manager.installed(m["id"])["installed"] and not manager.has_desktop_shortcut(m["id"])

def test_existing_unrelated_file_is_protected_with_alternate(manager, app_files):
    directory = configure(manager); directory.mkdir(parents=True)
    m = create_app(manager, app_files); manager.install(m["id"])
    target = directory / shortcut_filename(m); target.write_text("unrelated")
    with pytest.raises(ShortcutConflict) as error: manager.create_desktop_shortcut(m["id"])
    assert target.read_text() == "unrelated" and manager.registry.owner(target) is None
    alternative = manager.create_desktop_shortcut(m["id"], error.value.alternate)
    assert alternative != target and alternative.is_file()
    manager.uninstall(m["id"])
    assert target.read_text() == "unrelated" and not alternative.exists()

def test_other_component_ownership_collision(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    target = directory / shortcut_filename(m)
    manager.registry.db.execute("INSERT INTO ownership VALUES(?,?,?,?)", (str(target), "other-component", "digest", 0o755)); manager.registry.db.commit()
    with pytest.raises(ShortcutConflict): manager.create_desktop_shortcut(m["id"])

def test_uninstall_removes_only_owned_shortcut(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files, True); manager.install(m["id"])
    shortcut = Path(manager.installed(m["id"])["desktop_shortcut"]["path"])
    extra = directory / "Unrelated.desktop"; extra.write_text("untouched")
    manager.uninstall(m["id"])
    assert not shortcut.exists() and extra.read_text() == "untouched"
    assert directory.is_dir() and manager.paths.source(m["id"]).is_dir()

def test_removal_requires_receipt_even_for_same_filename(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    directory.mkdir(parents=True); target = directory / shortcut_filename(m); target.write_text("not owned")
    with pytest.raises(SafetyError): manager.remove_desktop_shortcut(m["id"])
    assert target.read_text() == "not owned"

def test_modified_shortcut_is_preserved(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    target = manager.create_desktop_shortcut(m["id"]); target.write_text("manual changes")
    with pytest.raises(SafetyError): manager.remove_desktop_shortcut(m["id"])
    with pytest.raises(SafetyError): manager.uninstall(m["id"])
    assert target.read_text() == "manual changes"

def test_old_desktop_path_cleanup_survives_xdg_change(manager, app_files):
    old = configure(manager); m = create_app(manager, app_files, True); manager.install(m["id"])
    shortcut = old / shortcut_filename(m)
    configure(manager, '$HOME/Nouveau Bureau')
    assert manager.has_desktop_shortcut(m["id"])
    manager.uninstall(m["id"])
    assert not shortcut.exists() and old.is_dir()

def test_remove_preference_survives_update(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files, True); manager.install(m["id"])
    manager.remove_desktop_shortcut(m["id"])
    manager.save_file(m["id"], "src/main.py", 'print("new version")\n'); manager.install(m["id"])
    assert not manager.has_desktop_shortcut(m["id"]) and not (directory / shortcut_filename(m)).exists()

def test_metadata_updates_and_disable_update_both_copies(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    shortcut = manager.create_desktop_shortcut(m["id"])
    manager.set_enabled(m["id"], False)
    assert shortcut.read_bytes() == manager.canonical_desktop(m).read_bytes()
    assert "Hidden=true" in shortcut.read_text() and not shortcut.stat().st_mode & 0o111
    manager.set_enabled(m["id"], True)
    assert shortcut.read_bytes() == manager.canonical_desktop(m).read_bytes() and shortcut.stat().st_mode & 0o111
    m["description"] = "Updated description"
    manager.save_file(m["id"], "manifest.json", json.dumps(m)); manager.install(m["id"])
    assert shortcut.read_bytes() == manager.canonical_desktop(m).read_bytes() and "Updated description" in shortcut.read_text()

def test_backup_restore_toggle_restores_complete_app(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    shortcut = manager.create_desktop_shortcut(m["id"])
    before_create = next(b for b in manager.backups.list() if b["reason"] == "Created desktop shortcut")
    manager.restore(before_create["backup_id"])
    assert not shortcut.exists() and not manager.has_desktop_shortcut(m["id"])
    assert (manager.paths.root(m) / "src/main.py").exists() and manager.canonical_desktop(m).exists()
    manager.create_desktop_shortcut(m["id"]); manager.remove_desktop_shortcut(m["id"])
    before_remove = next(b for b in manager.backups.list() if b["reason"].startswith("Removed desktop shortcut"))
    manager.restore(before_remove["backup_id"])
    assert shortcut.exists() and manager.has_desktop_shortcut(m["id"])

def test_missing_shortcut_can_be_recreated_or_removed(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    target = manager.create_desktop_shortcut(m["id"]); target.unlink()
    assert not manager.has_desktop_shortcut(m["id"])
    manager.create_desktop_shortcut(m["id"]); assert target.exists()
    target.unlink(); manager.remove_desktop_shortcut(m["id"])
    assert manager.installed(m["id"])["desktop_shortcut"] is None

def test_scripts_get_shared_canonical_launcher_on_demand(manager):
    configure(manager)
    m, files = template("Useful Command", "useful-command", "Python Script")
    manager.create(files); manager.install(m["id"])
    assert not manager.canonical_desktop(m).exists()
    shortcut = manager.create_desktop_shortcut(m["id"])
    assert manager.canonical_desktop(m).read_bytes() == shortcut.read_bytes()
    assert "Terminal=true" in shortcut.read_text()
    manager.set_enabled(m["id"], False); assert shortcut.read_bytes() == manager.canonical_desktop(m).read_bytes()
    manager.remove_desktop_shortcut(m["id"]); manager.install(m["id"])
    assert manager.canonical_desktop(m).exists() and not shortcut.exists()

def test_service_shortcut_rejected(manager):
    m, files = template("Service", "shortcut-service", "systemd User Service")
    m["desktop"] = {"createShortcut": True}
    with pytest.raises(SafetyError): manifest_parse(json.dumps(m))
    manager.create(files); manager.install(m["id"])
    with pytest.raises(SafetyError): manager.create_desktop_shortcut(m["id"])
    with pytest.raises(SafetyError): manager.plan_install(m["id"], create_shortcut=True)

@pytest.mark.parametrize("value", ["yes", 1, None, []])
def test_manifest_shortcut_boolean_required(app_files, value):
    m, _ = app_files; m["desktop"] = {"createShortcut": value}
    with pytest.raises(SafetyError): manifest_parse(json.dumps(m))

def test_stale_shortcut_preview_refuses_new_collision(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    plan = manager.plan_create_desktop_shortcut(m["id"])
    target = Path(plan["shortcut"]["path"]); target.parent.mkdir(parents=True); target.write_text("new unrelated file")
    with pytest.raises(ShortcutConflict): manager.create_desktop_shortcut(m["id"], expected=plan)
    assert target.read_text() == "new unrelated file"

def test_desktop_entry_valid_and_independent(manager, app_files):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    shortcut = manager.create_desktop_shortcut(m["id"])
    if shutil.which("desktop-file-validate"):
        result = subprocess.run(["desktop-file-validate", str(shortcut)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    assert "caelestia-dev-manager --" not in shortcut.read_text()
    result = subprocess.run([str(manager.paths.bin / m["id"])], capture_output=True, text=True, check=True)
    assert "Hello" in result.stdout

def test_desktop_filename_sanitized(app_files):
    m, _ = app_files; m["name"] = "../../My Utility"
    name = shortcut_filename(m)
    assert "/" not in name and not name.startswith(".")

def test_arbitrary_desktop_path_is_not_an_allowed_destination(manager, app_files):
    directory = configure(manager); m = create_app(manager, app_files)
    with pytest.raises(SafetyError): manager.paths.allowed(m, directory / "random.desktop")

@pytest.mark.parametrize("operation", ["create", "remove"])
def test_shortcut_commit_failure_restores_files_and_ownership(manager, app_files, monkeypatch, operation):
    configure(manager); m = create_app(manager, app_files); manager.install(m["id"])
    if operation == "remove": manager.create_desktop_shortcut(m["id"])
    receipts = manager.registry.files(m["id"])
    contents = {f["path"]: Path(f["path"]).read_bytes() for f in receipts}
    record = manager.installed(m["id"])
    save = manager.registry.save; failed = False
    def fail_once(new):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("Simulated registry commit failure")
        return save(new)
    monkeypatch.setattr(manager.registry, "save", fail_once)
    action = manager.create_desktop_shortcut if operation == "create" else manager.remove_desktop_shortcut
    with pytest.raises(OSError, match="commit failure"): action(m["id"])
    assert manager.registry.files(m["id"]) == receipts
    assert manager.installed(m["id"]) == record
    assert all(Path(path).read_bytes() == content for path, content in contents.items())
    assert manager.has_desktop_shortcut(m["id"]) == (operation == "remove")
    assert not manager.journal.exists()
