import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from backend.paths import SafetyError
from backend.store import Store, DEFAULT_REPOSITORY
from backend.store_policy import eligibility, CHANNELS
from backend.dependencies import fingerprint, dependency_diff


def test_channels_keep_separate_caches_and_default_stable(manager):
    store = Store(manager.paths)
    assert store.channel == 'Stable'
    stable = store.cache_path(); store.set_channel('Beta'); beta = store.cache_path()
    assert stable != beta and store.settings['branch'] == 'beta'
    store.set_channel('Development'); assert store.settings['branch'] == 'development'
    assert Store(manager.paths).settings['branch'] == 'development'
    with pytest.raises(SafetyError): store.set_channel('Unreviewed')


def test_pin_ignore_enforced_by_fresh_download_plan(manager, app_files):
    m, files = app_files; manager.create(files); manager.install(m['id'])
    installed = manager.registry.files(m['id'])
    changed = {**files, 'src/main.py': 'print("new snapshot")\n'}
    for prefs, status in [({'version': m['version']}, 'Pinned to version'), ({'ignored': True}, 'ignored'), ({'channel': 'Beta'}, 'Pinned to Beta')]:
        manager.set_update_policy(m['id'], **prefs)
        with pytest.raises(SafetyError, match=status): manager.plan_store_download(changed, DEFAULT_REPOSITORY, 'a' * 40)
        assert manager.registry.files(m['id']) == installed
    manager.set_update_policy(m['id'])
    plan = manager.plan_store_download(files, DEFAULT_REPOSITORY, 'a' * 40)
    manager.set_update_policy(m['id'], ignored=True)
    with pytest.raises(SafetyError, match='ignored'): manager.download_store_source(files, plan)


def test_beta_new_source_retains_channel_provenance(manager, app_files):
    m, files = app_files
    plan = manager.plan_store_download(files, DEFAULT_REPOSITORY, 'b' * 40, 'Beta')
    manager.download_store_source(files, plan)
    record = manager.registry.get(m['id'])
    assert record['store_policy']['channel'] == record['store_origin']['channel'] == 'Beta'
    assert record['store_origin']['commit'] == 'b' * 40
    assert not record['installed']
    assert manager.registry.history()[0]['component'] == m['id']


def test_restore_keeps_current_pin_policy(manager, app_files):
    m, files = app_files; manager.create(files); manager.install(m['id']); backup = manager.backup(m['id'])
    manager.set_update_policy(m['id'], ignored=True)
    manager.restore(backup['backup_id'])
    assert manager.registry.get(m['id'])['store_policy']['ignored']


def test_dependency_fingerprint_diff_and_stale_marker(manager, app_files):
    from tests.test_dependencies import component, metadata
    m = component(manager)
    target = manager.prepared_path(m); metadata(target, 'demo', '2')
    (target / 'bin').mkdir(parents=True); (target / 'bin/python').write_text('fake interpreter')
    marker = target.parent / 'prepared.json'
    marker.write_text(json.dumps({'dependencies': ['demo>=2'], 'fingerprint': fingerprint()}))
    assert manager.dependencies_prepared(m)
    data = json.loads(marker.read_text()); data['fingerprint']['python'] = '0.0.0'; marker.write_text(json.dumps(data))
    assert not manager.dependencies_prepared(m)
    assert dependency_diff({'dependencies': {'python': ['demo==1']}}, m)['added'] == ['demo>=2']


def test_python_requirement_blocks_preparation_before_download(manager, app_files):
    m, files = app_files; m['dependencies'] = {'python': ['demo']}; m['compatibility'] = {'python': '<2'}
    files['manifest.json'] = json.dumps(m)
    manager.create(files, draft=True)
    with pytest.raises(SafetyError, match='compatibility.python'): manager.prepare_dependencies(m['id'])
    assert not manager.prepared_path(m).exists()
    assert manager.registry.history()[0]['component'] == m['id']
    assert manager.registry.history()[0]['state'] == 'failed'


def test_launch_record_persists_and_pidfd_recheck_prevents_wrong_stop(manager, app_files, monkeypatch):
    m, files = app_files; files['src/main.py'] = 'import time\ntime.sleep(15)\n'
    manager.create(files); manager.install(m['id']); record = manager.installed(m['id'])
    pid = manager.runtime.launch(record)
    try:
        assert manager.runtime.launch_records(record)[0]['pid'] == pid
        deadline = time.monotonic() + 2
        while pid not in manager.runtime.processes(record) and time.monotonic() < deadline: time.sleep(.01)
        assert manager.runtime.app_state(record) == 'Running'
        actual = manager.runtime.identity
        calls, sent = [], []
        def changed(candidate, record):
            calls.append(candidate)
            return actual(candidate, record) if len(calls) <= 1 else None
        monkeypatch.setattr(manager.runtime, 'processes', lambda record: [pid])
        monkeypatch.setattr(manager.runtime, 'identity', changed)
        monkeypatch.setattr(signal, 'pidfd_send_signal', lambda *args: sent.append(args))
        manager.runtime.stop(record)
        assert not sent
        assert Path('/proc', str(pid)).exists()
    finally:
        os.kill(pid, signal.SIGTERM); os.waitpid(pid, 0)


def test_plan_review_uses_actual_destinations_and_not_marketing(manager, app_files):
    from backend.review import describe
    m, files = app_files; m['permissions'] = ['Marketing: no permissions needed']; files['manifest.json'] = json.dumps(m)
    manager.create(files); plan = manager.plan_install(m['id'])
    summary = describe(plan)
    assert 'exact files' in summary and 'Runtime access' in summary
    assert 'Marketing' not in summary and 'sandbox-enforced' in summary


def test_component_search_and_new_independent_templates(manager, app_files):
    from PySide6.QtWidgets import QApplication
    from app.main import Window
    from backend.templates import template
    from backend.validators import manifest_parse
    app = QApplication.instance() or QApplication([])
    m, files = app_files; manager.create(files)
    view = Window(manager); view.components_search.setText('does not exist')
    assert view.components.item(0).isHidden() and 'No components match' in view.component_info.toPlainText()
    view.components_search.setText('harmless'); assert not view.components.item(0).isHidden()
    view.close(); app.processEvents()
    for choice in ['Shell User Service', 'Caelestia Dashboard Page']:
        manifest, source = template('Sample', 'sample-component', choice)
        assert manifest_parse(source['manifest.json']) == manifest
        assert all('backend.manager' not in value and 'app.main' not in value for value in source.values())


def test_dependency_cache_is_private_and_explicit(manager, monkeypatch):
    from tests.test_dependencies import component, metadata
    m = component(manager); target = manager.prepared_path(m)
    commands = []
    def run(command, **kwargs):
        commands.append((command, kwargs))
        if 'venv' in command:
            (target / 'bin').mkdir(parents=True); (target / 'bin/python').write_text('fake')
        else: metadata(target, 'demo', '2')
        return subprocess.CompletedProcess(command, 0, '', '')
    monkeypatch.setattr('backend.manager.subprocess.run', run)
    manager.prepare_dependencies(m['id'])
    pip = commands[-1]
    assert Path(pip[1]['env']['PIP_CACHE_DIR']).is_relative_to(manager.paths.manager / 'package-cache')
    assert '--only-binary=:all:' in pip[0]
    receipt = json.loads((target.parent / 'prepared.json').read_text())
    assert receipt['fingerprint'] == fingerprint()


def test_stale_store_result_cannot_change_selected_channel(manager, app_files):
    from PySide6.QtWidgets import QApplication
    from app.main import Window
    from types import SimpleNamespace
    app = QApplication.instance() or QApplication([]); view = Window(manager); page = view.store_page
    page.generation = 3; page.worker = SimpleNamespace(generation=2)
    page.checked({'entries': [{'manifest': app_files[0], 'files': app_files[1], 'hash': manager.source_hash(app_files[1])}]})
    assert page.catalog is None
    page.worker = None
    # Queued delivery can outlive the worker's finished/deleteLater signal.
    page.checked({'entries': []}, generation=2); page.failed('old channel error', generation=2)
    assert page.catalog is None and page.last_error == ''
    view.close(); app.processEvents()


def test_launch_refuses_changed_launcher_and_symlink_entrypoint(manager, app_files, tmp_path):
    m, files = app_files; manager.create(files); manager.install(m['id']); record = manager.installed(m['id'])
    launcher = manager.paths.bin / m['id']; original = launcher.read_bytes()
    launcher.write_bytes(b'#!/bin/sh\necho unrelated\n')
    with pytest.raises(SafetyError, match='entry changed'): manager.runtime.launch(record)
    launcher.write_bytes(original)
    entry = manager.paths.root(m) / m['entrypoint']; entry.unlink()
    outside = tmp_path / 'outside.py'; outside.write_text('print("must not execute")')
    entry.symlink_to(outside)
    with pytest.raises(SafetyError, match='Symbolic'): manager.runtime.launch(record)
