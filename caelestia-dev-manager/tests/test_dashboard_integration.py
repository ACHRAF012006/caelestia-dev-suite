"""Shared dashboard lifecycle against pinned fixtures in temporary XDG roots."""
import json
from pathlib import Path
import pytest
from backend import dashboard_integration as host, dashboard_compat as compat, host_integration, timer_integration
from backend.paths import SafetyError
from backend.templates import template
from backend.validators import manifest_parse, validate
from backend.store import checked_files


@pytest.fixture
def dashboard_manager(manager, monkeypatch):
    fixture = Path(__file__).parent / 'fixtures/caelestia-kde'
    originals = {}
    for name in host.FILES:
        path = manager.paths.shell / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((fixture / name).read_bytes()); originals[name] = path.read_text()
    (manager.paths.shell / '.current_commit').write_text(compat.COMMIT)
    (manager.paths.shell / '.current_version').write_text('VERSION=v2.5.1')
    env = {'plugin_supported': True, 'caelestia_commit': compat.COMMIT}
    manager.environment = env
    monkeypatch.setattr('backend.manager.detect', lambda paths: env)
    return manager, originals


def add(m, id='test-notes', page_id=None, order=50):
    manifest, files = template(id.title(), id, 'Empty Caelestia Plugin')
    manifest['integration'] = {'target': 'caelestia-dashboard', 'dashboard': {'id': page_id or id, 'title': id.title(), 'icon': 'edit_note', 'component': 'DashboardPage.qml', 'order': order}}
    files['manifest.json'] = json.dumps(manifest)
    files['DashboardPage.qml'] = 'import QtQuick\nItem { required property var controller; property bool presentationActive: true; implicitWidth: 600; implicitHeight: 400 }\n'
    m.create(files)
    return manifest, files


def current(m): return {n: (m.paths.shell / n).read_text() for n in host.FILES}


def test_multiple_ordering_duplicate_ids_and_independent_removal(dashboard_manager):
    m, originals = dashboard_manager
    add(m, 'test-notes', order=50); m.install('test-notes')
    add(m, 'test-calendar', order=40); m.install('test-calendar')
    add(m, 'test-weather', order=50); m.install('test-weather')
    text = current(m)['modules/dashboard/Content.qml']
    assert text.index('id: "test-calendar"') < text.index('id: "test-notes"') < text.index('id: "test-weather"')
    before = current(m)
    add(m, 'duplicate', page_id='test-notes')
    with pytest.raises(SafetyError, match='Duplicate'): m.install('duplicate')
    assert current(m) == before
    m.uninstall('test-notes')
    assert set(host.read_receipt(m.paths)[0]['pages']) == {'test-calendar', 'test-weather'}
    m.uninstall('test-calendar'); m.uninstall('test-weather')
    assert current(m) == originals and not host.receipt_path(m.paths).exists()


def test_enable_disable_update_previous_restore_and_uninstall(dashboard_manager):
    m, originals = dashboard_manager
    manifest, files = add(m)
    m.install('test-notes'); backup = m.backup('test-notes')
    m.set_enabled('test-notes', False)
    assert (m.paths.root(manifest) / 'metadata.json.disabled').exists()
    manifest['version'] = '0.2.0'; manifest['integration']['dashboard']['title'] = 'Changed'
    meta = json.loads(files['metadata.json']); meta['version'] = '0.2.0'
    files.update({'manifest.json': json.dumps(manifest), 'metadata.json': json.dumps(meta)})
    for name, text in files.items(): m.save_file('test-notes', name, text)
    m.install('test-notes')
    assert not m.installed('test-notes')['enabled'] and 'Changed' in current(m)['modules/dashboard/Content.qml']
    prior = m.previous_version_backup('test-notes'); assert prior
    m.restore(prior['backup_id'])
    assert m.installed('test-notes')['installed_version'] == '0.1.0'
    m.set_enabled('test-notes', True); m.uninstall('test-notes')
    assert current(m) == originals
    m.restore(backup['backup_id'])
    assert host.read_receipt(m.paths)[0]['pages']['test-notes']['title'] == 'Test-Notes'
    m.uninstall('test-notes'); assert current(m) == originals


def test_timer_legacy_composition_and_receipt_reconstruction(dashboard_manager):
    m, originals = dashboard_manager
    source = Path(__file__).resolve().parents[1] / 'plugins/animated-timer'
    files = {p.relative_to(source).as_posix(): p.read_text() for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    m.create(files); m.install('animated-timer')
    legacy_raw = timer_integration.receipt_path(m.paths).read_text()
    legacy_host = current(m)
    add(m); m.install('test-notes')
    assert host.read_receipt(m.paths)[0]['timer']
    assert 'animatedTimerNotchLoader' in current(m)['modules/dashboard/Wrapper.qml']
    assert 'findIndex(tab => tab.id === "timer")' in current(m)['modules/dashboard/Content.qml']
    m.set_enabled('animated-timer', False); m.install('animated-timer'); m.set_enabled('animated-timer', True)
    m.uninstall('test-notes')
    assert current(m) == legacy_host
    assert timer_integration.receipt_path(m.paths).read_text() == legacy_raw
    assert not host.receipt_path(m.paths).exists()
    add(m, 'calendar'); m.install('calendar')
    timer_backup = m.backup('animated-timer'); m.uninstall('animated-timer')
    assert not host.read_receipt(m.paths)[0]['timer'] and 'animatedTimerNotchLoader' not in current(m)['modules/dashboard/Wrapper.qml']
    m.restore(timer_backup['backup_id']); assert host.read_receipt(m.paths)[0]['timer']
    m.uninstall('animated-timer'); m.uninstall('calendar'); assert current(m) == originals


def test_timer_installed_after_generic_page(dashboard_manager):
    m, originals = dashboard_manager
    add(m); m.install('test-notes')
    source = Path(__file__).resolve().parents[1] / 'plugins/animated-timer'
    m.create({p.relative_to(source).as_posix(): p.read_text() for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    m.install('animated-timer')
    assert host.read_receipt(m.paths)[0]['timer']
    m.uninstall('animated-timer'); m.uninstall('test-notes'); assert current(m) == originals


@pytest.mark.parametrize('mutation', ['content', 'mode', 'version', 'commit', 'receipt'])
def test_changed_host_fails_closed(dashboard_manager, mutation):
    m, _ = dashboard_manager
    add(m); m.install('test-notes')
    path = m.paths.shell / next(iter(host.FILES))
    if mutation == 'content': path.write_text(path.read_text() + '\n// third party\n')
    elif mutation == 'mode': path.chmod((path.stat().st_mode & 0o777) ^ 0o100)
    elif mutation == 'version': (m.paths.shell / '.current_version').write_text('VERSION=v2.6.0')
    elif mutation == 'commit': (m.paths.shell / '.current_commit').write_text('0' * 40)
    else: host.receipt_path(m.paths).write_text('{}')
    before = current(m)
    for operation in (lambda: m.install('test-notes'), lambda: m.uninstall('test-notes'), lambda: m.set_enabled('test-notes', False)):
        with pytest.raises(SafetyError): operation()
    assert current(m) == before and m.installed('test-notes')['enabled']


def test_unrelated_files_untouched_and_stale_membership_rejected(dashboard_manager):
    m, _ = dashboard_manager
    unrelated = m.paths.shell / 'User.qml'; unrelated.write_text('// user')
    add(m); preview = m.plan_install('test-notes')
    add(m, 'calendar'); m.install('calendar')
    with pytest.raises(SafetyError): m.install('test-notes', expected=preview)
    assert unrelated.read_text() == '// user'


@pytest.mark.parametrize('fail_at', ['Wrapper.qml', 'dashboard-pages.json', 'registry'])
def test_partial_transaction_rolls_back(dashboard_manager, monkeypatch, fail_at):
    m, originals = dashboard_manager; add(m)
    write, save = host.atomic_write, m.registry.save
    failed = False
    def once(path, data, mode=0o644):
        nonlocal failed
        if not failed and Path(path).name == fail_at:
            failed = True; raise OSError('injected failure')
        return write(path, data, mode)
    def registry_once(record):
        nonlocal failed
        if not failed: failed = True; raise OSError('injected registry failure')
        return save(record)
    monkeypatch.setattr(host, 'atomic_write', once)
    if fail_at == 'registry': monkeypatch.setattr(m.registry, 'save', registry_once)
    with pytest.raises(OSError): m.install('test-notes')
    assert current(m) == originals and not host.receipt_path(m.paths).exists()
    assert not m.registry.get('test-notes')['installed'] and not m.journal.exists()


def test_interrupted_migration_recovers_both_receipts(dashboard_manager):
    m, originals = dashboard_manager
    legacy = timer_integration.plan(m.paths, {'id': 'animated-timer', 'integration': {'target': timer_integration.TARGET}})
    timer_integration.apply(m.paths, legacy)
    before = current(m); raw = timer_integration.receipt_path(m.paths).read_text()
    manifest, _ = add(m)
    proposal = host.plan(m.paths, manifest); host.apply(m.paths, proposal)
    host.recover(m.paths, proposal)
    assert current(m) == before and timer_integration.receipt_path(m.paths).read_text() == raw
    assert not host.receipt_path(m.paths).exists()
    timer_integration.recover(m.paths, legacy); assert current(m) == originals


def test_recovery_preserves_third_party_changes(dashboard_manager):
    m, _ = dashboard_manager; manifest, _ = add(m)
    proposal = host.plan(m.paths, manifest); host.apply(m.paths, proposal)
    path = m.paths.shell / next(iter(host.FILES)); path.write_text(path.read_text() + '\n// external edit')
    with pytest.raises(SafetyError): host.recover(m.paths, proposal)
    assert 'external edit' in path.read_text()


def test_tampered_plan_not_executable(dashboard_manager):
    m, _ = dashboard_manager; manifest, _ = add(m)
    proposal = host.plan(m.paths, manifest)
    proposal['after'][next(iter(host.FILES))] += '\n// arbitrary code'
    with pytest.raises(SafetyError): host.apply(m.paths, proposal)
    with pytest.raises(SafetyError): host.recover(m.paths, proposal)


@pytest.mark.parametrize('field,value', [('component', '/tmp/page.qml'), ('component', '../Page.qml'), ('component', 'a/../Page.qml'), ('component', 'Page.qml"'), ('order', True), ('order', 0), ('icon', 'file:///tmp/x.svg'), ('id', 'timer'), ('title', 'Bad\nTitle'), ('patch', 'execute')])
def test_strict_contract(dashboard_manager, field, value):
    m, _ = dashboard_manager; manifest, files = add(m)
    manifest['integration']['dashboard'][field] = value
    with pytest.raises(SafetyError): manifest_parse(json.dumps(manifest))


def test_missing_page_store_and_validation(dashboard_manager):
    m, _ = dashboard_manager; manifest, files = add(m); del files['DashboardPage.qml']
    with pytest.raises(SafetyError): checked_files(files, manifest['id'])
    assert not validate(files, manifest)['valid']


def test_actual_interrupted_journal_recovery_preserves_other_page_and_user_data(dashboard_manager, monkeypatch):
    from backend.manager import Manager
    m, _ = dashboard_manager
    add(m, 'calendar'); m.install('calendar')
    before = current(m)
    data = m.paths.data / 'caelestia-components/notes-tasks/data.json'
    data.parent.mkdir(parents=True); data.write_text('{"personal":"retained"}')
    add(m)
    write = host.atomic_write
    def crash(path, content, mode=0o644):
        if Path(path).name == 'Wrapper.qml': raise SystemExit('simulated process crash')
        return write(path, content, mode)
    monkeypatch.setattr(host, 'atomic_write', crash)
    with pytest.raises(SystemExit): m.install('test-notes')
    assert m.journal.exists()
    monkeypatch.setattr(host, 'atomic_write', write)
    m.registry.db.close()
    restarted = Manager(m.paths, real=False)
    assert restarted.recover() == 'Previous installed state recovered'
    assert current(restarted) == before
    assert set(host.read_receipt(restarted.paths)[0]['pages']) == {'calendar'}
    assert data.read_text() == '{"personal":"retained"}'
    restarted.uninstall('calendar')
    assert data.exists()


def test_store_declaration_requires_manager_version(dashboard_manager):
    m, _ = dashboard_manager; manifest, files = add(m)
    manifest['compatibility'] = {'manager_min_version': '99.0.0'}
    result = validate(files, manifest)
    assert not result['valid'] and 'Requires Dev Manager 99.0.0' in '\n'.join(result['errors'])


def test_supported_sources_are_deterministic_across_install_order(dashboard_manager):
    m, originals = dashboard_manager
    pages = {'alpha': {'id': 'same-order-a', 'title': 'A', 'icon': 'edit_note', 'component': 'DashboardPage.qml', 'order': 50},
             'beta': {'id': 'same-order-b', 'title': 'B', 'icon': 'edit_note', 'component': 'DashboardPage.qml', 'order': 50}}
    assert compat.sources(originals, pages, False, m.paths) == compat.sources(originals, dict(reversed(list(pages.items()))), False, m.paths)
