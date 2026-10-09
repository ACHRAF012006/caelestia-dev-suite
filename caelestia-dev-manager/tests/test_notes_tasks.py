"""Domain/storage/helper tests use temporary XDG data, never production state."""
import importlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'plugins/notes-tasks'
sys.path.insert(0, str(SOURCE / 'helper'))
storage = importlib.import_module('storage')
domain = importlib.import_module('domain')


@pytest.fixture
def model(): return domain.Model(storage.empty())


def create(model, kind='notes', **values):
    delta = model.command({'action': 'create', 'kind': kind, 'values': values})
    return delta['changes'][0]['id']


def edit(model, kind, id, **values): return model.command({'action': 'edit', 'kind': kind, 'id': id, 'values': values})


def test_notes_create_edit_pin_archive_duplicate_search_delete_and_restart(tmp_path, model):
    id = create(model, title='', text='Thoughts 🌿 عربية', tags=['work', 'work', ' study '])
    original = model.rows['notes'][id]
    assert original['content'] == {'format': 'plain', 'text': 'Thoughts 🌿 عربية'}
    assert original['tags'] == ['work', 'study'] and original['createdAt']
    edit(model, 'notes', id, title='Title', pinned=True, archived=True)
    dto = model.snapshot()['notes'][0]
    assert 'thoughts' in dto['searchText'] and 'work' in dto['searchText'] and dto['archived']
    copy = model.command({'action': 'duplicate', 'kind': 'notes', 'id': id})['changes'][0]['id']
    assert copy != id and not model.rows['notes'][copy]['archived']
    edit(model, 'notes', id, archived=False)
    store = storage.Store(tmp_path); store.save(model.persisted()); store.close()
    store = storage.Store(tmp_path); restored = domain.Model(store.read()); store.close()
    assert restored.snapshot() == model.snapshot()
    model.command({'action': 'delete', 'kind': 'notes', 'id': id})
    assert id not in model.rows['notes'] and copy in model.rows['notes']


def test_tasks_edit_complete_uncomplete_reorder_subtasks_and_restart(tmp_path, model):
    a = create(model, 'tasks', title='Project')
    b = create(model, 'tasks', title='Study')
    c = create(model, 'tasks', title='Third')
    edit(model, 'tasks', a, due={'date': '2026-10-09', 'time': '14:30'}, priority=3, details='Details', tags=['work'])
    model.command({'action': 'subtask-create', 'kind': 'tasks', 'id': a, 'title': 'Part one'})
    sub = model.rows['tasks'][a]['subtasks'][0]['id']
    model.command({'action': 'subtask-toggle', 'kind': 'tasks', 'id': a, 'subtaskId': sub})
    model.command({'action': 'subtask-edit', 'kind': 'tasks', 'id': a, 'subtaskId': sub, 'title': 'Renamed'})
    assert model.rows['tasks'][a]['subtasks'][0] == {'id': sub, 'title': 'Renamed', 'completed': True}
    edit(model, 'tasks', a, completed=True)
    completed_at = model.rows['tasks'][a]['completedAt']
    assert completed_at and edit(model, 'tasks', a, completed=True) is None
    edit(model, 'tasks', a, completed=False)
    assert model.rows['tasks'][a]['completedAt'] == ''
    model.command({'action': 'reorder', 'kind': 'tasks', 'id': c, 'before': a})
    assert sorted(model.rows['tasks'], key=lambda i: model.rows['tasks'][i]['order']) == [c, a, b]
    model.command({'action': 'reorder', 'kind': 'tasks', 'id': c, 'before': None})
    assert sorted(model.rows['tasks'], key=lambda i: model.rows['tasks'][i]['order']) == [a, b, c]
    store = storage.Store(tmp_path); store.save(model.persisted()); store.close()
    store = storage.Store(tmp_path); assert domain.Model(store.read()).snapshot() == model.snapshot(); store.close()
    model.command({'action': 'subtask-delete', 'kind': 'tasks', 'id': a, 'subtaskId': sub})
    assert not model.rows['tasks'][a]['subtasks']
    model.command({'action': 'delete', 'kind': 'tasks', 'id': b}); assert b not in model.rows['tasks']


@pytest.mark.parametrize('values', [{'due': {'date': '2026-02-30', 'time': ''}}, {'due': {'date': '', 'time': '12:00'}}, {'due': {'date': '2026-01-01', 'time': '25:00'}}, {'priority': True}, {'tags': [42]}, {'subtasks': [{'id': 'x'}]}, {'order': 3}, {'recurrence': 'unsupported'}])
def test_invalid_edit_is_transactional(model, values):
    id = create(model, 'tasks', title='Retained')
    before = model.snapshot()
    with pytest.raises(storage.StorageError): edit(model, 'tasks', id, **values)
    assert model.snapshot() == before


def test_preferences_and_extension_data_survive_restart(tmp_path, model):
    id = create(model, 'tasks')
    model.rows['tasks'][id]['extensions'] = {'future': {'remoteId': 'abc'}}
    model.command({'action': 'settings', 'values': {'animation': False, 'compact': True, 'noteSort': 'title'}})
    store = storage.Store(tmp_path); store.save(model.persisted()); store.close()
    store = storage.Store(tmp_path); data = store.read(); store.close()
    assert data['settings']['animation'] is False and data['tasks'][0]['extensions']['future']['remoteId'] == 'abc'


def test_atomic_save_backup_failure_and_external_edit(tmp_path, monkeypatch, model):
    store = storage.Store(tmp_path); create(model, text='First'); store.save(model.persisted())
    before = store.path.read_bytes()
    id = next(iter(model.rows['notes'])); edit(model, 'notes', id, text='Second')
    replace = os.replace
    def fail(source, destination):
        if Path(destination) == store.path: raise OSError('injected power failure before replace')
        return replace(source, destination)
    monkeypatch.setattr(storage.os, 'replace', fail)
    with pytest.raises(OSError): store.save(model.persisted())
    assert store.path.read_bytes() == before and store.backup.read_bytes() == before
    assert not list(tmp_path.glob('.save-*'))
    monkeypatch.setattr(storage.os, 'replace', replace); store.save(model.persisted())
    assert store.backup.read_bytes() == before
    store.path.write_text('external modification')
    with pytest.raises(storage.StorageError, match='outside'): store.save(model.persisted())
    assert store.path.read_text() == 'external modification'; store.close()


@pytest.mark.parametrize('raw,error', [('{broken', storage.StorageError), ('{"schemaVersion":2,"notes":[],"tasks":[]}', storage.UnsupportedSchema), ('{"schemaVersion":0}', storage.UnsupportedSchema), ('[]', storage.StorageError)])
def test_malformed_and_unsupported_preserved(tmp_path, raw, error):
    (tmp_path / 'data.json').write_text(raw)
    store = storage.Store(tmp_path)
    with pytest.raises(error): store.read()
    assert store.path.read_text() == raw; store.close()


def test_migration_framework_does_not_mutate_or_skip_versions():
    original = {'schemaVersion': 1, 'value': 'keep'}
    def one(value): value['schemaVersion'] = 2; value['added'] = True; return value
    def two(value): value['schemaVersion'] = 3; return value
    assert storage.migrate(original, target=3, migrations={1: one, 2: two}) == {'schemaVersion': 3, 'value': 'keep', 'added': True}
    assert original == {'schemaVersion': 1, 'value': 'keep'}
    with pytest.raises(storage.UnsupportedSchema): storage.migrate(original, target=3, migrations={1: one})
    with pytest.raises(storage.StorageError): storage.migrate(original, target=2, migrations={1: lambda x: {**x, 'schemaVersion': 3}})


def test_exclusive_writer(tmp_path):
    first = storage.Store(tmp_path)
    with pytest.raises(storage.StorageError, match='writer'): storage.Store(tmp_path)
    first.close(); second = storage.Store(tmp_path); second.close()


def test_hundreds_notes_thousands_tasks_incremental(model):
    for i in range(300): create(model, title=f'Note {i}', text='content')
    for i in range(2000): create(model, 'tasks', title=f'Task {i}')
    id = next(iter(model.rows['tasks']))
    delta = edit(model, 'tasks', id, completed=True)
    assert len(delta['changes']) == 1
    assert len(model.snapshot()['tasks']) == 2000


def test_helper_debounce_rapid_commands_restart_and_multiple_clients(tmp_path):
    env = dict(os.environ, XDG_DATA_HOME=str(tmp_path))
    def spawn(): return subprocess.Popen([sys.executable, '-B', str(SOURCE / 'helper/main.py')], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    class Client:
        def __init__(self, proc): self.proc = proc; self.buffer = b''
        def receive(self, timeout=4):
            deadline = time.monotonic() + timeout
            with selectors.DefaultSelector() as sel:
                sel.register(self.proc.stdout, selectors.EVENT_READ)
                while b'\n' not in self.buffer:
                    assert sel.select(max(0, deadline - time.monotonic())), 'helper response timed out'
                    chunk = os.read(self.proc.stdout.fileno(), 65536); assert chunk, self.proc.stderr.read().decode()
                    self.buffer += chunk
                line, self.buffer = self.buffer.split(b'\n', 1); return json.loads(line)
        def send(self, message): self.proc.stdin.write(json.dumps(message).encode() + b'\n'); self.proc.stdin.flush()
    proc = spawn(); other = None
    try:
        a, b = Client(proc), Client(proc)  # Two dashboard clients share one writer/protocol.
        assert a.receive()['type'] == 'snapshot'
        a.send({'action': 'create', 'kind': 'notes', 'values': {'text': 'first'}})
        id = a.receive()['changes'][0]['id']
        file = tmp_path / 'caelestia-components/notes-tasks/data.json'
        assert not file.exists()  # edit acknowledged before debounce write
        for i in range(100):
            (a if i % 2 else b).send({'action': 'edit', 'kind': 'notes', 'id': id, 'values': {'text': f'edit {i}'}})
            delta = a.receive(); assert delta['changes'][0]['row']['text'] == f'edit {i}'
        saved = a.receive(); assert saved['type'] == 'saved'
        assert json.loads(file.read_text())['notes'][0]['content']['text'] == 'edit 99'
        # Once idle there are no periodic snapshots or writes.
        with selectors.DefaultSelector() as sel:
            sel.register(proc.stdout, selectors.EVENT_READ); assert not sel.select(0.2)
        other = spawn(); other.communicate(timeout=4); assert other.returncode == 2
        b.send({'action': 'edit', 'kind': 'notes', 'id': id, 'values': {'title': 'Pending shutdown edit'}})
        assert a.receive()['type'] == 'delta'
        proc.terminate(); proc.communicate(timeout=4); assert proc.returncode == 0
        proc = spawn(); a = Client(proc)
        restored = a.receive(); assert restored['notes'][0]['title'] == 'Pending shutdown edit'
        a.send({'action': 'quit'}); proc.communicate(timeout=4); assert proc.returncode == 0
    finally:
        for p in (proc, other):
            if p and p.poll() is None: p.kill(); p.wait(timeout=4)


@pytest.mark.parametrize('raw', ['{"schemaVersion":1,"schemaVersion":2}', '{"schemaVersion":1,"revision":NaN}', '{"schemaVersion":1,"revision":Infinity}'])
def test_non_json_and_duplicate_keys_are_preserved(tmp_path, raw):
    (tmp_path / 'data.json').write_text(raw)
    store = storage.Store(tmp_path)
    with pytest.raises(storage.StorageError): store.read()
    assert store.path.read_text() == raw; store.close()


def test_relative_xdg_root_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME', 'relative-to-repository')
    monkeypatch.setenv('HOME', str(tmp_path))
    store = storage.Store()
    assert store.path == tmp_path / '.local/share/caelestia-components/notes-tasks/data.json'
    store.close()
