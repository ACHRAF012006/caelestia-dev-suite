"""All lifecycle mutations use pytest's isolated XDG sandbox."""
import importlib.util
import json
from pathlib import Path
import pytest
from backend import timer_integration as host
from backend.paths import SafetyError
from backend.store import checked_files
from backend.validators import manifest_parse

SOURCE = Path(__file__).resolve().parents[1] / 'plugins/animated-timer'
spec = importlib.util.spec_from_file_location('timer_engine_test', SOURCE / 'src/engine.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Clock:
    boot = 'boot-1'
    value = 1000.0
    wall_value = 100000.0
    def now(self): return self.value
    def wall(self): return self.wall_value
    def advance(self, seconds):
        self.value += seconds
        self.wall_value += seconds


@pytest.fixture
def engine(tmp_path):
    notifications = []
    engine = module.Engine(tmp_path / 'timer/state.json', Clock(), notifications.append)
    return engine, engine.clock, notifications


def test_deadline_accuracy_and_pause_resume(engine):
    e, c, _ = engine
    e.command({'action': 'configure', 'seconds': 10})
    e.command({'action': 'start'})
    c.advance(3.125)
    e.command({'action': 'pause'})
    assert e.remaining() == pytest.approx(6.875)
    c.advance(999)
    assert e.remaining() == pytest.approx(6.875)
    e.command({'action': 'resume'})
    c.advance(6.875)
    assert e.tick()
    assert e.snapshot()['state'] == 'Completed'


def test_config_and_presets_do_not_change_countdown(engine):
    e, c, _ = engine
    e.command({'action': 'start'})
    c.advance(17)
    for _ in range(30):
        e.command({'action': 'adjust', 'unit': 1, 'delta': 1})
    e.command({'action': 'preset-save', 'name': 'Custom', 'seconds': 30})
    custom = e.data['presets'][-1]
    e.command({'action': 'preset-save', 'id': custom['id'], 'name': 'Renamed', 'seconds': 45})
    assert e.data['presets'][-1]['name'] == 'Renamed'
    e.command({'action': 'preset-delete', 'id': custom['id']})
    assert e.remaining() == 1483
    assert e.data['configured'] == 3300
    e.command({'action': 'reset'})
    assert e.remaining() == 3300
    assert e.data['state'] == 'Ready'


def test_suspend_and_restart_exactly_one_completion(engine):
    e, c, events = engine
    e.command({'action': 'configure', 'seconds': 5})
    e.command({'action': 'start'})
    c.advance(3600)  # CLOCK_BOOTTIME includes suspend.
    restored = module.Engine(e.path, c, events.append)
    assert restored.data['state'] == 'Completed'
    assert len(events) == 1
    for _ in range(20): restored.tick()
    module.Engine(e.path, c, events.append)
    assert len(events) == 1


def test_running_restored_without_wall_clock_drift(engine):
    e, c, events = engine
    e.command({'action': 'start'})
    c.advance(45)
    c.wall_value += 86400
    assert module.Engine(e.path, c, events.append).remaining() == 1455
    c.boot = 'boot-2'
    c.value = 2
    assert module.Engine(e.path, c, events.append).data['state'] == 'Completed'


def test_rapid_commands_are_idempotent_and_atomic(engine):
    e, c, events = engine
    for _ in range(20): e.command({'action': 'start'})
    cycle = e.data['cycle']
    c.advance(3)
    for _ in range(20): e.command({'action': 'pause'})
    assert e.remaining() == 1497
    for _ in range(20): e.command({'action': 'resume'})
    assert e.data['cycle'] == cycle
    for _ in range(20): e.command({'action': 'reset'})
    assert e.remaining() == 1500
    e.command({'action': 'cancel'})
    assert not events


def test_auto_repeat_does_not_replay_suspend_cycles(engine):
    e, c, events = engine
    e.command({'action': 'configure', 'seconds': 2})
    e.command({'action': 'preferences', 'values': {'repeat': True}})
    e.command({'action': 'start'})
    cycle = e.data['cycle']
    c.advance(10000)
    e.tick()
    assert len(events) == 1
    assert e.data['cycle'] != cycle and e.remaining() == 2


@pytest.fixture
def timer_manager(manager, monkeypatch):
    fixtures = Path(__file__).parent / 'fixtures/caelestia-kde'
    originals = {}
    for name in host.FILES:
        path = manager.paths.shell / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((fixtures / name).read_bytes())
        originals[name] = path.read_text()
    (manager.paths.shell / '.current_commit').write_text(host.COMMIT)
    (manager.paths.shell / '.current_version').write_text('VERSION=v2.5.1\n')
    env = {'plugin_supported': True, 'caelestia_commit': host.COMMIT}
    monkeypatch.setattr('backend.manager.detect', lambda paths: env)
    manager.environment = env
    files = {p.relative_to(SOURCE).as_posix(): p.read_text() for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    manager.create(files)
    return manager, originals


def test_timer_install_disable_update_backup_restore_uninstall(timer_manager):
    m, originals = timer_manager
    plan = m.plan_install('animated-timer')
    assert 'BEFORE' in plan['preview'] and 'AFTER' in plan['preview']
    m.install('animated-timer', expected=plan)
    assert m.installed('animated-timer')['enabled']
    assert m.status(m.installed('animated-timer'))['host_integration_status'] == 'Timer dashboard installed'
    backup = m.backup('animated-timer')
    m.set_enabled('animated-timer', False)
    m.install('animated-timer')
    assert not m.installed('animated-timer')['enabled']
    m.set_enabled('animated-timer', True)
    m.uninstall('animated-timer')
    assert all((m.paths.shell / n).read_text() == v for n, v in originals.items())
    m.restore(backup['backup_id'])
    assert host.receipt_path(m.paths).is_file()
    m.uninstall('animated-timer')
    assert not host.receipt_path(m.paths).exists()
    assert all('quickshell/caelestia/' not in f['path'] for f in m.registry.files('animated-timer'))


def test_timer_rejects_unexpected_host_and_stale_preview(timer_manager):
    m, _ = timer_manager
    plan = m.plan_install('animated-timer')
    p = m.paths.shell / next(iter(host.FILES))
    p.write_text(p.read_text() + '\n// unrelated customization\n')
    with pytest.raises(SafetyError): m.install('animated-timer', expected=plan)
    assert 'customization' in p.read_text()


def test_timer_post_install_edits_are_preserved(timer_manager):
    m, _ = timer_manager
    m.install('animated-timer')
    p = m.paths.shell / next(iter(host.FILES))
    p.write_text(p.read_text() + '\n// user edit\n')
    with pytest.raises(SafetyError): m.uninstall('animated-timer')
    assert 'user edit' in p.read_text() and m.installed('animated-timer')['installed']


def test_timer_partial_host_write_recovers(timer_manager, monkeypatch):
    m, originals = timer_manager
    write = host.atomic_write
    failed = False
    def once(path, data, mode=0o644):
        nonlocal failed
        if not failed and Path(path).name == 'Wrapper.qml':
            failed = True
            raise OSError('partial timer write')
        return write(path, data, mode)
    monkeypatch.setattr(host, 'atomic_write', once)
    with pytest.raises(OSError): m.install('animated-timer')
    assert all((m.paths.shell / n).read_text() == v for n, v in originals.items())
    assert not host.receipt_path(m.paths).exists()


def test_timer_registry_failure_recovers(timer_manager, monkeypatch):
    m, originals = timer_manager
    save = m.registry.save
    failed = False
    def once(record):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError('registry failure')
        return save(record)
    monkeypatch.setattr(m.registry, 'save', once)
    with pytest.raises(OSError): m.install('animated-timer')
    assert all((m.paths.shell / n).read_text() == v for n, v in originals.items())
    assert not m.registry.get('animated-timer')['installed']


def test_timer_rejects_release_and_receipt_corruption(timer_manager):
    m, _ = timer_manager
    (m.paths.shell / '.current_version').write_text('VERSION=v2.6.0')
    with pytest.raises(SafetyError): m.plan_install('animated-timer')
    (m.paths.shell / '.current_version').write_text('VERSION=v2.5.1')
    m.install('animated-timer')
    p = host.receipt_path(m.paths)
    receipt = json.loads(p.read_text()); receipt['originals'][next(iter(host.FILES))] += '// edit'
    p.write_text(json.dumps(receipt))
    with pytest.raises(SafetyError): m.uninstall('animated-timer')


def test_other_components_cannot_claim_timer_adapter():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    manifest['id'] = 'other-component'
    with pytest.raises(SafetyError): manifest_parse(json.dumps(manifest))


def test_store_mapping():
    files = {p.relative_to(SOURCE).as_posix(): p.read_text() for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    checked_files(files, 'animated-timer')


def test_invalid_state_is_retained_for_diagnosis(engine):
    e, c, events = engine
    e.command({'action': 'start'})
    data = json.loads(e.path.read_text()); data['deadline'] = float('nan')
    e.path.write_text(json.dumps(data))
    restored = module.Engine(e.path, c, events.append)
    assert restored.data['state'] == 'Ready'
    assert len(list(e.path.parent.glob('state-invalid-*.json'))) == 1


def test_helper_restart_and_exclusive_lock(tmp_path):
    import os
    import subprocess
    import sys
    import time
    env = dict(os.environ, XDG_STATE_HOME=str(tmp_path))
    def spawn():
        return subprocess.Popen([sys.executable, '-B', str(SOURCE / 'src/main.py')], env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    helper = spawn()
    duplicate = None
    try:
        assert json.loads(helper.stdout.readline())['state'] == 'Ready'
        for command in ({'action': 'preferences', 'values': {'sound': False, 'notification': False}},
                        {'action': 'configure', 'seconds': 10}, {'action': 'start'}):
            helper.stdin.write(json.dumps(command) + '\n'); helper.stdin.flush()
            snapshot = json.loads(helper.stdout.readline())
        cycle = snapshot['cycle']
        duplicate = spawn()
        duplicate.communicate(timeout=5)
        assert duplicate.returncode == 2
        helper.stdin.write('{"action":"quit"}\n'); helper.stdin.flush()
        helper.wait(timeout=3)
        helper = spawn()
        snapshot = json.loads(helper.stdout.readline())
        assert snapshot['cycle'] == cycle and snapshot['state'] == 'Running'
        assert 0 < snapshot['remaining'] < 10
        helper.stdin.write('{"action":"cancel"}\n'); helper.stdin.flush()
        assert json.loads(helper.stdout.readline())['state'] == 'Ready'
    finally:
        for process in (helper, duplicate):
            if process and process.poll() is None:
                process.terminate(); process.wait(timeout=3)


def test_timer_recovery_preserves_third_party_edits(timer_manager):
    m, _ = timer_manager
    proposal = host.plan(m.paths, m.registry.get('animated-timer')['manifest'])
    host.apply(m.paths, proposal)
    p = m.paths.shell / next(iter(host.FILES))
    p.write_text(p.read_text() + '\n// recovery edit\n')
    with pytest.raises(SafetyError): host.recover(m.paths, proposal)
    assert 'recovery edit' in p.read_text()


def test_timer_host_mode_edit_blocks_uninstall(timer_manager):
    m, _ = timer_manager
    m.install('animated-timer')
    p = m.paths.shell / next(iter(host.FILES))
    mode = p.stat().st_mode & 0o777
    p.chmod(mode ^ 0o100)
    with pytest.raises(SafetyError): m.uninstall('animated-timer')
    assert p.stat().st_mode & 0o777 == mode ^ 0o100
