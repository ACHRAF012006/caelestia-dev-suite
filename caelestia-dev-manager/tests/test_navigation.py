import json
import threading
import time

import pytest
from PySide6.QtCore import Qt, QTimer, QAbstractAnimation
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.main import Window, STYLE
from app.inspection import Inspection
from backend.manager import Manager
from backend.paths import SafetyError, atomic_write
from backend.store import Store, DEFAULT_REPOSITORY


@pytest.fixture
def window(manager, app_files):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    _, files = app_files
    manager.create(files)
    view = Window(manager); view.show(); app.processEvents()
    yield view
    view.close()
    deadline = time.monotonic() + 3
    while view.refresh_worker is not None and time.monotonic() < deadline:
        QTest.qWait(10)
    app.processEvents()


def wait_until(predicate):
    deadline = time.monotonic() + 4
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
        # Yield the GIL as well as pumping Qt so Python inspection workers run.
        time.sleep(0.001)
    assert predicate()


def test_navigation_reuses_data_without_rescanning_files_or_backups(window, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Expensive check during navigation")
    for name in ("all_status", "dependency_status", "read_source"):
        monkeypatch.setattr(window.manager, name, forbidden)
    monkeypatch.setattr(window.manager.backups, "list", forbidden)
    monkeypatch.setattr(window.manager.backups, "catalog", forbidden)
    monkeypatch.setattr(window.store_page, "fill", forbidden)
    monkeypatch.setattr("backend.environment.detect", forbidden)
    for _ in range(3):
        for name in ("Components", "Backups", "Logs", "Settings", "Component Store", "Codex Context", "Dashboard"):
            window.navigate(name)
            assert window.stack.currentIndex() == window.nav.currentRow()
    assert "harmless-test" in window.context_editor.toPlainText()
    assert window.refresh_worker is None


def test_background_inspection_keeps_event_loop_and_tabs_responsive(window, monkeypatch):
    manager = window.manager
    entered, release = threading.Event(), threading.Event()
    original = Manager.status
    main_thread = threading.get_ident()
    threads = []
    ui_threads = []
    apply_snapshot = window.apply_snapshot
    def apply_on_ui(snapshot, ready=True):
        ui_threads.append(threading.get_ident())
        apply_snapshot(snapshot, ready)
    monkeypatch.setattr(window, "apply_snapshot", apply_on_ui)
    def slow_status(reader, record):
        threads.append(threading.get_ident()); entered.set()
        release.wait(2)
        return original(reader, record)
    monkeypatch.setattr(Manager, "status", slow_status)
    monkeypatch.setattr("app.inspection.detect", lambda paths: dict(manager.environment))
    ticks = []; timer = QTimer(window); timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1)); timer.start()
    try:
        window.request_refresh(); wait_until(entered.is_set)
        for name in ("Settings", "Components", "Backups", "Dashboard"):
            window.navigate(name); QTest.qWait(25)
            assert window.stack.currentIndex() == window.nav.currentRow()
        assert len(ticks) >= 3 and window.refresh_worker is not None
        assert threads and all(thread != main_thread for thread in threads)
    finally:
        release.set(); timer.stop()
    wait_until(lambda: window.refresh_worker is None)
    assert window.metrics["Components"].text() == "1"
    assert window.current_id == "harmless-test"
    assert ui_threads == [main_thread]


def test_frozen_inspection_never_uses_main_sqlite_connection(window, monkeypatch):
    manager = window.manager
    worker = Inspection(manager, 1, window)
    def forbidden(*args): raise AssertionError("Main-thread registry accessed from worker")
    for name in ("get", "files", "owner", "all", "logs"):
        monkeypatch.setattr(manager.registry, name, forbidden)
    monkeypatch.setattr("app.inspection.detect", lambda paths: dict(manager.environment))
    snapshots, errors = [], []
    worker.result.connect(lambda generation, snapshot: snapshots.append(snapshot))
    worker.failed.connect(lambda generation, message: errors.append(message))
    worker.start()
    wait_until(lambda: not worker.isRunning())
    QApplication.processEvents()
    assert not errors and snapshots[0]["statuses"][0]["id"] == "harmless-test"
    assert snapshots[0]["dependencies"]["harmless-test"]["development"]["ready"]


def test_old_results_cannot_replace_state_after_install(window):
    old_generation = window.refresh_generation
    window.confirm = lambda *args: True
    window.install_selected()
    assert window.manager.installed("harmless-test")["installed"]
    assert window.metrics["Installed"].text() == "1"
    window.inspected(old_generation, {})  # A late, obsolete result must not even be read.
    assert window.metrics["Installed"].text() == "1"


def test_failed_inspection_retains_loaded_data(window, monkeypatch):
    before = window.statuses
    monkeypatch.setattr("app.inspection.detect", lambda paths: (_ for _ in ()).throw(OSError("Temporary inspection failure")))
    window.request_refresh()
    wait_until(lambda: window.refresh_worker is None)
    assert window.statuses is before
    assert "Temporary inspection failure" in window.statusBar().currentMessage()
    window.navigate("Components")
    assert window.current_id == "harmless-test"


def test_rapid_switches_finish_cleanly_and_animation_preference_persists(window, manager):
    for index in (2, 1, 4, 5, 3, 6, 0, 7): window.nav.setCurrentRow(index)
    assert window.stack.animation.state() == QAbstractAnimation.Running
    assert window.stack.overlay.testAttribute(Qt.WA_TransparentForMouseEvents)
    QTest.qWait(200)
    assert window.stack.overlay.isHidden()
    assert window.stack.currentWidget().graphicsEffect() is None
    window.navigate("Dashboard"); window.resize(1040, 760); QApplication.processEvents()
    assert window.stack.overlay.isHidden()
    atomic_write(manager.paths.config / "caelestia-dev-manager/settings.json", b'{"editor": "kate"}')
    window.animations_setting.setChecked(False)
    assert not window.stack.animations_enabled
    assert not window.nav.animations_enabled
    window.navigate("Settings"); assert window.stack.overlay.isHidden()
    saved = json.loads((manager.paths.config / "caelestia-dev-manager/settings.json").read_text())
    assert saved == {"editor": "kate", "animations_enabled": False}
    reopened = Window(manager)
    assert not reopened.stack.animations_enabled and not reopened.animations_setting.isChecked()
    assert not reopened.nav.animations_enabled
    reopened.close()


def test_highlight_slides_and_rapid_mouse_keyboard_switches_stay_immediate(window):
    nav = window.nav
    start = nav.highlight.geometry()
    nav.setCurrentRow(4)
    target = nav.target_rect()
    assert nav.animation.state() == QAbstractAnimation.Running
    assert nav.highlight.geometry() == start
    nav.animation.setCurrentTime(65)
    middle = nav.highlight.geometry()
    assert start.y() < middle.y() < target.y()
    assert nav.highlight.testAttribute(Qt.WA_TransparentForMouseEvents)
    QTest.mouseClick(nav.viewport(), Qt.LeftButton, pos=nav.visualItemRect(nav.item(2)).center())
    assert nav.currentRow() == window.stack.currentIndex() == 2
    assert nav.animation.startValue() == middle
    QTest.keyClick(nav, Qt.Key_Down)
    assert nav.currentRow() == window.stack.currentIndex() == 3
    QTest.qWait(230)
    assert nav.highlight.geometry() == nav.target_rect()
    assert nav.animation.state() == QAbstractAnimation.Stopped
    window.resize(1040, 760); QApplication.processEvents()
    assert nav.highlight.geometry() == nav.target_rect()
    nav.setCurrentRow(6)
    window.animations_setting.setChecked(False)
    assert nav.highlight.geometry() == nav.target_rect()
    nav.setCurrentRow(0)
    assert nav.highlight.geometry() == nav.target_rect()
    assert nav.animation.state() == QAbstractAnimation.Stopped


def test_backup_catalogue_does_not_read_blobs_but_restore_still_checks_them(manager, app_files, monkeypatch):
    m, files = app_files; manager.create(files); manager.install(m["id"])
    backup = manager.backup(m["id"])
    owned = next(f for f in backup["files"] if f["exists"])
    blob = manager.paths.backups / backup["backup_id"] / owned["blob"]
    blob.write_bytes(b"tampered payload")
    def forbidden(*args): raise AssertionError("Backup blobs read for display")
    with monkeypatch.context() as patch:
        patch.setattr("backend.backups.digest", forbidden)
        catalog = manager.backups.catalog()
        assert any(item["backup_id"] == backup["backup_id"] for item in catalog)
        assert all("files" not in item for item in catalog)
    with pytest.raises(SafetyError, match="checksum"):
        manager.plan_restore(backup["backup_id"])


def test_cached_healthy_status_never_bypasses_install_ownership_checks(window):
    window.confirm = lambda *args: True; window.install_selected()
    manager = window.manager
    path = manager.paths.root(manager.installed("harmless-test")["manifest"]) / "src/main.py"
    path.write_text("print('manual edit to installed files')\n")
    assert not window.statuses[0]["modified"]
    with pytest.raises(SafetyError, match="Installed file was modified"):
        manager.plan_install("harmless-test")


def test_closing_cancels_background_inspection_without_using_terminate(window, monkeypatch):
    entered = threading.Event()
    def until_cancelled(reader, record):
        entered.set()
        while not window.refresh_worker.cancelled.wait(.01): pass
        window.refresh_worker.checkpoint()
    monkeypatch.setattr(Manager, "status", until_cancelled)
    monkeypatch.setattr("app.inspection.detect", lambda paths: dict(window.manager.environment))
    window.request_refresh(); wait_until(entered.is_set)
    window.close(); wait_until(lambda: window.refresh_worker is None)
    assert window.closing


def test_repeated_refresh_requests_coalesce_instead_of_starting_parallel_checks(window, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = Manager.status
    def slow_status(reader, record):
        calls.append(record["id"]); entered.set(); release.wait(2)
        return original(reader, record)
    monkeypatch.setattr(Manager, "status", slow_status)
    monkeypatch.setattr("app.inspection.detect", lambda paths: dict(window.manager.environment))
    try:
        window.request_refresh(); wait_until(entered.is_set)
        first = window.refresh_worker
        for _ in range(10): window.request_refresh()
        assert window.refresh_worker is first and window.refresh_pending
    finally:
        release.set()
    wait_until(lambda: window.refresh_worker is None)
    assert calls == ["harmless-test", "harmless-test"]


def test_real_startup_displays_window_before_background_inspection(manager, app_files, monkeypatch):
    app = QApplication.instance() or QApplication([])
    _, files = app_files; manager.create(files)
    Store(manager.paths).save_settings(DEFAULT_REPOSITORY, "main", False)
    manager.runtime.real = True
    def forbidden(): raise AssertionError("Startup blocked on a synchronous full inspection")
    monkeypatch.setattr(manager, "all_status", forbidden)
    monkeypatch.setattr("app.inspection.detect", lambda paths: dict(manager.environment))
    view = Window(manager)
    assert view.refresh_worker is None and view.statuses == []
    app.clipboard().setText("Keep existing clipboard")
    assert view.copy_context() is False
    assert app.clipboard().text() == "Keep existing clipboard"
    view.show()
    wait_until(lambda: view.refresh_worker is None and len(view.statuses) == 1)
    assert view.isVisible() and view.metrics["Components"].text() == "1"
    assert view.snapshot_ready
    view.close(); app.processEvents()
