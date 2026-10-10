import json
import threading
import time
from pathlib import Path
import subprocess
import sys
import pytest
from backend.jobs import JobManager, Job, JobContext
from backend.diagnostics import inspect


def test_bounded_jobs_cancel_queued_and_report_errors():
    pool = JobManager(concurrency=1)
    entered, release = threading.Event(), threading.Event()
    first = pool.submit(Job('slow'), lambda ctx: (entered.set(), release.wait(3)))
    assert entered.wait(1)
    ran = []
    queued = pool.submit(Job('queued', generation=2), lambda ctx: ran.append(1))
    assert queued.state == 'queued' and queued.cancel()
    release.set(); first.future.result(3); queued.future.result(3)
    assert first.state == 'succeeded' and queued.state == 'cancelled' and not ran
    bad = pool.submit(Job('failure'), lambda ctx: (_ for _ in ()).throw(ValueError('https://name:password@host/?token=secret')))
    bad.future.result(3)
    assert bad.state == 'failed' and bad.error['category'] == 'ValueError'
    assert 'password' not in bad.error['message'] and 'secret' not in bad.error['message']
    pool.shutdown()


def test_mutating_job_cannot_be_cancelled():
    pool = JobManager(concurrency=1)
    entered, release = threading.Event(), threading.Event()
    job = Job('reviewed mutation', context=JobContext(cancellable=False))
    pool.submit(job, lambda ctx: (entered.set(), release.wait(2)))
    assert entered.wait(1) and job.cancel() is False
    release.set(); job.future.result(3); assert job.state == 'succeeded'
    pool.shutdown()


def test_diagnostics_read_only_reports_corrupt_backup(manager, app_files):
    m, files = app_files; manager.create(files); manager.install(m['id']); backup = manager.backup(m['id'])
    (manager.paths.backups / backup['backup_id'] / '0').write_bytes(b'corrupt')
    before = manager.registry.all(), manager.registry.files(m['id']), manager.registry.history()
    result = inspect(manager.paths, real=False)
    assert result['database_schema'] == 2
    assert any(c['scope'] == 'Backup' and c['status'] == 'Failed' for c in result['checks'])
    assert before == (manager.registry.all(), manager.registry.files(m['id']), manager.registry.history())


def test_cli_does_not_create_state_or_import_qt(tmp_path):
    from backend.paths import Paths
    paths = Paths.sandbox(tmp_path)
    command = [sys.executable, '-m', 'backend.cli', '--sandbox', str(tmp_path), '--json', 'doctor']
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)['database_schema'] is None
    assert not paths.database.exists() and not paths.manager.exists()
    from backend.cli import main
    assert main(['--sandbox', str(tmp_path), 'list']) == 0


def test_cli_validate_and_history_ui(manager, app_files):
    from backend.cli import main
    from PySide6.QtWidgets import QApplication
    from app.main import Window
    m, files = app_files; manager.create(files); manager.install(m['id'])
    root = manager.paths.project.parent
    assert main(['--sandbox', str(root), 'validate', m['id']]) == 0
    app = QApplication.instance() or QApplication([])
    window = Window(manager); window.navigate('Operation History')
    assert 'Installed component' in window.history_editor.toPlainText()
    window.navigate('Diagnostics'); assert 'System Health' in window.diagnostics_editor.toPlainText()
    window.close(); app.processEvents()


def test_reviewed_background_job_keeps_qt_responsive_and_owns_connection(manager, app_files, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from app.main import Window
    from backend.manager import Manager
    app = QApplication.instance() or QApplication([])
    m, files = app_files; manager.create(files)
    view = Window(manager)
    main_thread = threading.get_ident(); ticks = []
    def slow(reader):
        assert threading.get_ident() != main_thread
        assert reader.registry.db is not manager.registry.db
        assert reader.registry.get(m['id'])
        time.sleep(.12)
        return 'verified'
    monkeypatch.setattr(Manager, 'job_probe', slow, raising=False)
    timer = QTimer(view); timer.setInterval(10); timer.timeout.connect(lambda: ticks.append(1)); timer.start()
    assert view.run_backend('Verify test state', 'job_probe', cancellable=True) == 'verified'
    timer.stop(); assert len(ticks) >= 3
    view.close(); app.processEvents()
