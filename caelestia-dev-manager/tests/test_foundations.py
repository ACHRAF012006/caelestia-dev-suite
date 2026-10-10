import copy
import json
import sqlite3
from pathlib import Path
import pytest
from backend.paths import SafetyError
from backend.schemas import decode, CURRENT_SCHEMA
from backend.registry import Registry
from backend.database import CURRENT_VERSION


def test_manifest_migration_is_pure_preserves_original(app_files):
    m, _ = app_files
    m.pop('schema_version', None)
    text = json.dumps(m)
    doc = decode(text)
    assert doc.source_version == 1 and doc.migrations == ((1, 2),)
    assert doc.manifest['schema_version'] == CURRENT_SCHEMA
    assert doc.original == m and doc.original_text == text
    assert decode(text) == doc
    assert decode(json.dumps(doc.manifest)).migrations == ()


@pytest.mark.parametrize('version', [3, 99, True, 1.0, 0, '2'])
def test_future_or_invalid_schema_fails_with_version(app_files, version):
    with pytest.raises(SafetyError, match='schema_version.*unsupported schema'):
        decode(json.dumps({**app_files[0], 'schema_version': version}))


def test_schema_field_errors_and_strict_legacy(app_files):
    with pytest.raises(SafetyError, match='schema 1.*Unknown.*resources'):
        decode(json.dumps({**app_files[0], 'schema_version': 1, 'resources': {}}))
    with pytest.raises(SafetyError, match='schema 2.*resources.*sha256'):
        decode(json.dumps({**app_files[0], 'schema_version': 2, 'resources': {'a.bin': {'sha256': 'bad', 'mime': 'application/octet-stream'}}}))
    with pytest.raises(SafetyError, match='Duplicate'):
        decode('{"schema_version":1,"schema_version":2}')


@pytest.mark.parametrize('field,value', [('type', []), ('runtime', {}), ('desktop', {'categories': 1}),
                                       ('service', {'restart': []}), ('portable_data', [{'root': [], 'path': 'x'}])])
def test_schema_invalid_field_types_report_schema_and_field(app_files, field, value):
    with pytest.raises(SafetyError, match='schema 2: ' + field):
        decode(json.dumps({**app_files[0], 'schema_version': 2, field: value}))


def test_legacy_database_upgrade_backed_up(tmp_path):
    path = tmp_path / 'db.sqlite'
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE components(id TEXT PRIMARY KEY, record TEXT NOT NULL); CREATE TABLE ownership(path TEXT PRIMARY KEY, component TEXT NOT NULL, checksum TEXT NOT NULL, mode INTEGER NOT NULL); CREATE TABLE events(time TEXT NOT NULL, component TEXT, message TEXT NOT NULL);')
    db.execute('INSERT INTO components VALUES(?,?)', ('example', '{"id":"example"}'))
    db.commit(); db.close()
    registry = Registry(path)
    assert registry.get('example') == {'id': 'example'}
    assert registry.db.execute('PRAGMA user_version').fetchone()[0] == CURRENT_VERSION
    backups = list((tmp_path / 'database-backups').glob('*.sqlite3'))
    assert len(backups) == 1
    old = sqlite3.connect(backups[0])
    assert old.execute('PRAGMA user_version').fetchone()[0] == 0
    assert old.execute('SELECT record FROM components').fetchone()
    old.close(); registry.db.close()
    Registry(path).db.close()
    assert len(list((tmp_path / 'database-backups').glob('*'))) == 1


def test_newer_database_is_not_mutated(tmp_path):
    path = tmp_path / 'new.sqlite'
    db = sqlite3.connect(path); db.execute('PRAGMA user_version=99'); db.close()
    before = path.read_bytes()
    with pytest.raises(SafetyError, match='newer'): Registry(path)
    assert path.read_bytes() == before


def test_unknown_database_and_corruption_fail_closed(tmp_path):
    path = tmp_path / 'unknown.sqlite'
    db = sqlite3.connect(path); db.execute('CREATE TABLE personal(secret TEXT)'); db.close()
    with pytest.raises(SafetyError, match='Unrecognized'): Registry(path)
    path.write_bytes(b'broken database')
    with pytest.raises(SafetyError, match='preserve'): Registry(path)


def test_payload_recovery_preserves_crash_time_edit(manager, app_files, monkeypatch):
    from backend.installers import FilePlan
    m, files = app_files; manager.create(files); manager.install(m['id'])
    manager.save_file(m['id'], 'src/main.py', 'print("new")\n')
    original = FilePlan.content
    def crash(plan):
        if manager.journal.exists(): raise SystemExit('power loss')
        return original(plan)
    monkeypatch.setattr(FilePlan, 'content', crash)
    with pytest.raises(SystemExit): manager.install(m['id'])
    payload = manager.paths.root(m) / 'README.md'
    payload.write_text('third party edit')
    with pytest.raises(SafetyError, match='changed during'): manager.recover()
    assert payload.read_text() == 'third party edit' and manager.journal.exists()


def test_backup_rechecked_when_used(manager, app_files):
    m, files = app_files; manager.create(files); manager.install(m['id'])
    backup = manager.backup(m['id']); item = next(f for f in backup['files'] if f['exists'])
    (manager.paths.backups / backup['backup_id'] / item['blob']).write_bytes(b'corrupt after preview')
    with pytest.raises(SafetyError, match='checksum'): manager.backups.content(backup, item)


def test_recovery_refuses_external_deletion_during_replacement(manager, app_files, monkeypatch):
    from backend.installers import FilePlan
    m, files = app_files; manager.create(files); manager.install(m['id'])
    original = FilePlan.content
    def crash(plan):
        if manager.journal.exists(): raise SystemExit('power loss')
        return original(plan)
    monkeypatch.setattr(FilePlan, 'content', crash)
    with pytest.raises(SystemExit): manager.install(m['id'])
    deleted = manager.paths.root(m) / 'README.md'; deleted.unlink()
    with pytest.raises(SafetyError, match='Missing recovery file'): manager.recover()
    assert not deleted.exists() and manager.journal.exists()


def test_cast_tampered_plan_and_recovery_rejected(manager):
    from backend import host_integration as host
    fixture = Path(__file__).parent / 'fixtures/caelestia-kde'
    for name in host.FILES:
        path = manager.paths.shell / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((fixture / name).read_bytes())
    plan = host.plan(manager.paths, {'id': 'cast-audio', 'integration': {'target': host.TARGET}})
    plan['after'][next(iter(host.FILES))] = 'arbitrary hostile host code'
    with pytest.raises(SafetyError, match='transformation'): host.check(manager.paths, plan)
    with pytest.raises(SafetyError, match='transformation'): host.recover(manager.paths, plan)


def test_structured_history_and_redaction(manager, app_files):
    m, files = app_files; manager.create(files); manager.install(m['id'])
    event = manager.registry.history()[0]
    assert event['component'] == m['id'] and event['state'] == 'succeeded'
    assert event['transaction_id'] == manager.installed(m['id'])['last_operation']
    with manager.registry.db: manager.registry.log(m['id'], 'https://user:secret@test/token?key=secret password=hidden')
    assert 'secret' not in manager.registry.logs()[0] and 'hidden' not in manager.registry.logs()[0]


def test_capability_registry_refuses_unknown_code_and_hosts(manager):
    from backend.capabilities import capabilities
    from backend.compatibility import inspect, COMMIT
    from backend import host_integration as host
    assert set(capabilities.types) == {'standalone-app', 'script', 'user-service', 'caelestia-plugin', 'qml-component', 'kde-integration'}
    with pytest.raises(SafetyError, match='Unknown manager-owned'):
        host.apply(manager.paths, {'id': 'import:evil.py'})
    assert inspect(manager.paths, 'future')['status'] == 'Adapter update required'
    assert inspect(manager.paths, 'animated-timer')['status'] == 'Unsupported'
    fixture = Path(__file__).parent / 'fixtures/caelestia-kde'
    for name in host.FILES:
        path = manager.paths.shell / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((fixture / name).read_bytes())
    assert inspect(manager.paths, 'cast-audio')['status'] == 'Compatible by verified signature'
    (manager.paths.shell / '.current_version').write_text('v2.6.0')
    (manager.paths.shell / '.current_commit').write_text(COMMIT)
    assert inspect(manager.paths, 'cast-audio')['status'] == 'Unsupported'
    with pytest.raises(SafetyError, match='verified Caelestia'):
        host.plan(manager.paths, {'id': 'cast-audio', 'integration': {'target': host.TARGET}})


def test_transactional_database_upgrade_failure_rolls_back(tmp_path):
    from backend.database import migrate
    path = tmp_path / 'version-one.sqlite'
    db = sqlite3.connect(path)
    db.executescript('CREATE TABLE components(id TEXT PRIMARY KEY, record TEXT NOT NULL); CREATE TABLE ownership(path TEXT PRIMARY KEY, component TEXT NOT NULL, checksum TEXT NOT NULL, mode INTEGER NOT NULL); CREATE TABLE events(time TEXT NOT NULL, component TEXT, message TEXT NOT NULL); PRAGMA user_version=1;')
    # Simulate a DDL failure after operations is created, before version commit.
    db.set_authorizer(lambda action, a, b, c, d: sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_INDEX else sqlite3.SQLITE_OK)
    with pytest.raises(SafetyError, match='migration failed'): migrate(db, path)
    assert db.execute('PRAGMA user_version').fetchone()[0] == 1
    assert not db.execute("SELECT name FROM sqlite_master WHERE name='operations'").fetchone()
    db.set_authorizer(None); migrate(db, path)
    assert db.execute('PRAGMA user_version').fetchone()[0] == 2
    db.close()


def test_restore_rechecks_compatibility_and_empty_ownership_is_reported(manager, app_files, monkeypatch):
    m, files = app_files; manager.create(files); manager.install(m['id']); backup = manager.backup(m['id'])
    backup_manifest = backup['record']['installed_manifest']
    backup_manifest['compatibility'] = {'plasma': '999'}
    from backend.paths import atomic_write
    metadata = manager.paths.backups / backup['backup_id'] / 'metadata.json'
    atomic_write(metadata, json.dumps(backup).encode())
    with pytest.raises(SafetyError, match='compatibility'): manager.plan_restore(backup['backup_id'])
    with manager.registry.db: manager.registry.replace_files(m['id'], [])
    status = manager.status(manager.registry.get(m['id']))
    assert status['status'] == 'Broken' and any('ownership receipt' in p for p in status['modified'])


def test_portable_data_is_narrow_declaration_and_hooks_are_rejected(app_files):
    m = {**app_files[0], 'schema_version': 2, 'portable_data': [{'root': 'data', 'path': 'caelestia-components/harmless-test/settings.json'}]}
    assert decode(json.dumps(m)).manifest['portable_data'] == m['portable_data']
    for path in ['../../private', 'cast-audio/settings.json', 'caelestia-components/another-id/settings.json']:
        with pytest.raises(SafetyError): decode(json.dumps({**m, 'portable_data': [{'root': 'data', 'path': path}]}))
    with pytest.raises(SafetyError, match='Unknown'):
        decode(json.dumps({**m, 'data_migrations': [{'run': 'arbitrary-python.py'}]}))


def test_special_backup_blob_and_future_journal_fail_closed(manager, app_files):
    import os
    m, files = app_files; manager.create(files); manager.install(m['id']); backup = manager.backup(m['id'])
    path = manager.paths.backups / backup['backup_id'] / '0'; path.unlink(); os.mkfifo(path)
    with pytest.raises(SafetyError, match='regular file'): manager.backups.read(backup['backup_id'])
    manager.journal.write_text(json.dumps({'journal_version': 99}))
    with pytest.raises(SafetyError, match='journal version'): manager.recover()
    assert manager.journal.exists()
