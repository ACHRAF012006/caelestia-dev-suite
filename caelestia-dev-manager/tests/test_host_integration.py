import json
from pathlib import Path
import pytest

from backend import host_integration as host
from backend.paths import SafetyError
from backend.templates import template


@pytest.fixture
def cast_manager(manager, monkeypatch):
    fixtures = Path(__file__).parent / "fixtures/caelestia-kde"
    originals = {}
    for name in host.FILES:
        path = manager.paths.shell / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((fixtures / name).read_bytes())
        originals[name] = path.read_text()
    environment = {"plugin_supported": True}
    monkeypatch.setattr("backend.manager.detect", lambda paths: environment)
    manager.environment = environment
    manifest, files = template("Cast Audio", "cast-audio", "Empty Caelestia Plugin")
    manifest["integration"] = {"target": host.TARGET}
    files["manifest.json"] = json.dumps(manifest)
    manager.create(files)
    return manager, originals


def test_install_integrates_and_uninstall_restores_host(cast_manager):
    manager, originals = cast_manager
    plan = manager.plan_install("cast-audio")
    assert "BEFORE" in plan["preview"] and "AFTER" in plan["preview"]
    manager.install("cast-audio", expected=plan)
    assert manager.installed("cast-audio")["enabled"]
    assert "castAudioMenuLoader" in (manager.paths.shell / next(iter(host.FILES))).read_text()
    assert host.receipt_path(manager.paths).is_file()
    # Ordinary payload ownership never claims the host's entire source tree.
    assert all("quickshell/caelestia/" not in f["path"] for f in manager.registry.files("cast-audio"))
    manager.uninstall("cast-audio")
    assert not host.receipt_path(manager.paths).exists()
    assert all((manager.paths.shell / name).read_text() == value for name, value in originals.items())
    assert manager.paths.source("cast-audio").is_dir()


def test_stale_preview_and_unrelated_host_edits_are_preserved(cast_manager):
    manager, originals = cast_manager
    preview = manager.plan_install("cast-audio")
    path = manager.paths.shell / next(iter(host.FILES))
    path.write_text(path.read_text() + "\n// unrelated edit\n")
    with pytest.raises(SafetyError):
        manager.install("cast-audio", expected=preview)
    assert not manager.registry.get("cast-audio")["installed"]
    assert "unrelated edit" in path.read_text()


def test_edits_after_install_block_uninstall_without_deleting_source(cast_manager):
    manager, _ = cast_manager
    manager.install("cast-audio")
    path = manager.paths.shell / next(iter(host.FILES))
    path.write_text(path.read_text() + "\n// local customization\n")
    with pytest.raises(SafetyError, match="host file changed"):
        manager.uninstall("cast-audio")
    assert manager.installed("cast-audio")["installed"]
    assert "local customization" in path.read_text()


def test_registry_failure_rolls_back_payload_host_and_receipt(cast_manager, monkeypatch):
    manager, originals = cast_manager
    save = manager.registry.save
    failed = False
    def fail_once(record):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated commit failure")
        return save(record)
    monkeypatch.setattr(manager.registry, "save", fail_once)
    with pytest.raises(OSError, match="simulated"):
        manager.install("cast-audio")
    assert not manager.registry.get("cast-audio")["installed"]
    assert not manager.journal.exists()
    assert not host.receipt_path(manager.paths).exists()
    assert all((manager.paths.shell / name).read_text() == value for name, value in originals.items())


def test_restore_after_uninstall_recreates_menu_and_preserves_disabled_updates(cast_manager):
    manager, _ = cast_manager
    manager.install("cast-audio")
    backup = manager.backup("cast-audio")
    manager.uninstall("cast-audio")
    manager.restore(backup["backup_id"])
    assert host.receipt_path(manager.paths).exists()
    manager.set_enabled("cast-audio", False)
    manager.install("cast-audio")
    assert not manager.installed("cast-audio")["enabled"]


def test_install_requests_shell_restart_after_transaction(cast_manager, monkeypatch):
    manager, _ = cast_manager
    calls = []
    manager.runtime.real = True
    monkeypatch.setattr(manager.runtime, "systemctl", lambda *args: calls.append(args) or "")
    manager.install("cast-audio")
    assert ("restart", "caelestia-shell.service") in calls
    assert not manager.installed("cast-audio")["reload_required"]


def test_partial_host_write_failure_recovers_both_files(cast_manager, monkeypatch):
    manager, originals = cast_manager
    from backend import quick_toggle_integration
    write = quick_toggle_integration.atomic_write
    failed = False
    def fail_once(path, data, mode=0o644):
        nonlocal failed
        if not failed and Path(path).name == "QuickTogglesPage.qml":
            failed = True
            raise OSError("partial host write")
        return write(path, data, mode)
    monkeypatch.setattr(quick_toggle_integration, "atomic_write", fail_once)
    with pytest.raises(OSError, match="partial host"):
        manager.install("cast-audio")
    assert all((manager.paths.shell / name).read_text() == value for name, value in originals.items())
    assert not manager.registry.get("cast-audio")["installed"]


def test_adapter_never_accepts_other_component_ids(manager):
    with pytest.raises(SafetyError, match="Cast Audio only"):
        host.plan(manager.paths, {"id": "other-plugin", "integration": {"target": host.TARGET}})


def test_receipt_checksum_corruption_is_refused(cast_manager):
    manager, _ = cast_manager
    manager.install('cast-audio')
    path = host.receipt_path(manager.paths)
    receipt = json.loads(path.read_text())
    receipt['checksums'][next(iter(host.FILES))] = '0' * 64
    path.write_text(json.dumps(receipt))
    with pytest.raises(SafetyError, match='Invalid host integration receipt'):
        manager.uninstall('cast-audio')
    assert manager.installed('cast-audio')['installed']


def test_changed_host_mode_blocks_removal(cast_manager):
    manager, _ = cast_manager
    manager.install('cast-audio')
    path = manager.paths.shell / next(iter(host.FILES))
    original_mode = path.stat().st_mode & 0o777
    path.chmod(original_mode ^ 0o100)
    with pytest.raises(SafetyError, match='changed after integration'):
        manager.uninstall('cast-audio')
    assert path.stat().st_mode & 0o777 == original_mode ^ 0o100
