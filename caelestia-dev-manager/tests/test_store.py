import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

from app.main import Window
from backend.paths import SafetyError
from backend.store import Store, DEFAULT_REPOSITORY, checked_settings, checked_files, source_hash, describe_entry


COMMIT = "a" * 40


def git(directory, *args, input=None):
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Store Test",
                           "-c", "user.email=store-test@example.invalid", "-C", str(directory), *args],
                          check=True, capture_output=True, text=True, input=input).stdout.strip()


@pytest.fixture
def repository(tmp_path, app_files):
    directory = tmp_path / "remote"
    directory.mkdir()
    git(directory, "init", "-b", "main")
    _, files = app_files
    for name, text in files.items():
        target = directory / "components/harmless-test" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    git(directory, "add", ".")
    git(directory, "commit", "-m", "Initial components")
    return directory


def local_store(manager, repository):
    class LocalStore(Store):
        def git(self, *args, **kwargs):
            if args[0] == "fetch":
                args = tuple(str(repository) if x == self.settings["repository"] else x for x in args)
                # Local fixture transport only; production still forbids file:// URLs.
                args = ("-c", "protocol.file.allow=always", *args)
            return super().git(*args, **kwargs)
    return LocalStore(manager.paths)


def test_real_git_scan_cache_and_update_do_not_execute_source(manager, repository):
    marker = repository.parent / "must-not-exist"
    source = repository / "components/harmless-test/src/main.py"
    source.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
    (repository / "components/README.md").write_text("# Published components\n")
    git(repository, "add", "."); git(repository, "commit", "-m", "Inert source")
    store = local_store(manager, repository)
    first = store.scan()
    assert len(first["entries"]) == 1
    assert first["issues"] == []
    entry = first["entries"][0]
    assert entry["hash"] == source_hash(entry["files"])
    assert not marker.exists() and not manager.paths.source("harmless-test").exists()
    assert store.cached() == first
    source.write_text("print('updated source')\n")
    git(repository, "add", "."); git(repository, "commit", "-m", "Update")
    second = store.scan()
    assert second["commit"] != first["commit"] and second["entries"][0]["hash"] != entry["hash"]
    assert not marker.exists()


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_git_symlink_and_submodule_objects_are_refused(manager, repository, mode):
    obj = git(repository, "hash-object", "-w", "--stdin", input="../../outside") if mode == "120000" else git(repository, "rev-parse", "HEAD")
    git(repository, "update-index", "--add", "--cacheinfo", mode + "," + obj + ",components/harmless-test/unsafe")
    git(repository, "commit", "-m", "Unsafe inert tree entry")
    catalog = local_store(manager, repository).scan()
    assert catalog["entries"] == []
    assert "Symlinks, submodules" in catalog["issues"][0]
    assert not manager.paths.source("harmless-test").exists()


def test_unsafe_paths_and_invalid_manifests_do_not_enter_store(manager, repository):
    hidden = repository / "components/harmless-test/.hidden"
    hidden.write_text("inert")
    git(repository, "add", "."); git(repository, "commit", "-m", "Hidden file")
    catalog = local_store(manager, repository).scan()
    assert not catalog["entries"] and "Unsafe component file path" in catalog["issues"][0]


@pytest.mark.parametrize("repository", ["file:///tmp/repo", "https://other.example/a/b.git", "https://secret@github.com/a/b.git", "git@github.com:a/b.git", "https://github.com/a/b.git --upload-pack=evil", None])
def test_repository_urls_are_constrained(repository):
    with pytest.raises(SafetyError):
        checked_settings({"repository": repository, "branch": "main", "check_on_startup": True})


@pytest.mark.parametrize("branch", ["../main", "main:other", "--main", "main.lock", "main//other", "main/", "main\n"])
def test_branch_validation(branch):
    with pytest.raises(SafetyError):
        checked_settings({"repository": DEFAULT_REPOSITORY, "branch": branch, "check_on_startup": True})


def test_binary_reserved_paths_and_python_syntax_are_refused(app_files):
    _, files = app_files
    for name, value in (("src/binary.txt", "bad\0data"), ("_venv/bin/python", "inert"), ("../escape", "inert"), ("src/main.py", "invalid python : !")):
        bad = {**files, name: value}
        with pytest.raises(SafetyError): checked_files(bad)


def test_store_download_is_reviewed_source_only_and_update_keeps_backup(manager, app_files):
    m, files = app_files
    plan = manager.plan_store_download(files, DEFAULT_REPOSITORY, COMMIT)
    assert not manager.paths.source(m["id"]).exists()
    manager.download_store_source(files, plan)
    assert manager.read_source(m["id"]) == files
    assert not manager.registry.get(m["id"])["installed"]
    assert not (manager.paths.bin / m["id"]).exists()
    manager.install(m["id"])
    installed = {f["path"]: Path(f["path"]).read_bytes() for f in manager.registry.files(m["id"])}
    changed = {**files, "src/main.py": "print('new version')\n"}
    manifest = copy.deepcopy(m); manifest["version"] = "0.2.0"
    changed["manifest.json"] = json.dumps(manifest)
    updated = manager.plan_store_download(changed, DEFAULT_REPOSITORY, "b" * 40)
    manager.download_store_source(changed, updated)
    assert manager.read_source(m["id"]) == changed
    assert all(Path(path).read_bytes() == text for path, text in installed.items())
    assert manager.status(manager.registry.get(m["id"]))["source_modified"]
    backups = list((manager.paths.manager / "source-backups").glob("*/harmless-test/src/main.py"))
    assert len(backups) == 1 and backups[0].read_text() == files["src/main.py"]


def test_local_source_collision_and_edits_are_protected(manager, app_files):
    m, files = app_files
    manager.create(files)
    changed = {**files, "src/main.py": "print('remote')\n"}
    with pytest.raises(SafetyError, match="local source"):
        manager.plan_store_download(changed, DEFAULT_REPOSITORY, COMMIT)
    manager.download_store_source(files, manager.plan_store_download(files, DEFAULT_REPOSITORY, COMMIT))
    manager.save_file(m["id"], "src/main.py", "print('my edit')\n")
    with pytest.raises(SafetyError, match="Local source has edits"):
        manager.plan_store_download(changed, DEFAULT_REPOSITORY, COMMIT)
    assert manager.read_source(m["id"])["src/main.py"] == "print('my edit')\n"


def test_stale_store_review_and_failed_swap_preserve_source(manager, app_files, monkeypatch):
    m, files = app_files
    manager.download_store_source(files, manager.plan_store_download(files, DEFAULT_REPOSITORY, COMMIT))
    changed = {**files, "src/main.py": "print('remote')\n"}
    plan = manager.plan_store_download(changed, DEFAULT_REPOSITORY, "b" * 40)
    altered = {**changed, "src/extra.py": "print('unreviewed')\n"}
    with pytest.raises(SafetyError, match="changed since"):
        manager.download_store_source(altered, plan)
    original_rename = os.rename
    def fail_place(source, target):
        if Path(source).name.startswith("store-"): raise OSError("simulated rename failure")
        return original_rename(source, target)
    monkeypatch.setattr(os, "rename", fail_place)
    with pytest.raises(OSError, match="simulated"):
        manager.download_store_source(changed, plan)
    assert manager.read_source(m["id"]) == files
    assert manager.registry.get(m["id"])["store_origin"]["commit"] == COMMIT


def test_corrupt_cache_and_missing_git_degrade_gracefully(manager, monkeypatch):
    store = Store(manager.paths)
    store.cache_path().parent.mkdir(parents=True)
    store.cache_path().write_text("{broken")
    assert store.cached() is None and store.notice
    monkeypatch.setattr("backend.store.shutil.which", lambda name: None)
    with pytest.raises(SafetyError, match="Git is missing"): store.scan()


def test_cancelled_git_request_is_not_started(manager):
    store = Store(manager.paths)
    store.cancelled.set()
    with pytest.raises(SafetyError, match="cancelled"): store.git("version")


def test_store_ui_async_failure_cache_search_and_review(manager, app_files, monkeypatch):
    app = QApplication.instance() or QApplication([])
    m, files = app_files
    entry = {"manifest": m, "files": files, "hash": source_hash(files)}
    catalog = {"repository": DEFAULT_REPOSITORY, "branch": "main", "commit": COMMIT,
               "checked_at": "test", "entries": [entry], "issues": []}
    store = Store(manager.paths)
    store.cache_path().parent.mkdir(parents=True)
    store.cache_path().write_text(json.dumps(catalog))
    window = Window(manager)
    page = window.store_page
    assert page.list.count() == 1
    page.search.setText("no match"); assert page.list.count() == 0
    page.search.setText("Harmless"); assert page.list.count() == 1
    reviews = []
    window.confirm = lambda *args: reviews.append(args) or False
    page.download()
    assert "src/main.py" in reviews[0][1]
    assert not manager.paths.source(m["id"]).exists()
    window.confirm = lambda *args: True
    page.download()
    assert manager.paths.source(m["id"]).exists() and page.install_button.isEnabled()
    monkeypatch.setattr(Store, "scan", lambda self: (_ for _ in ()).throw(SafetyError("Offline test")))
    page.check()
    assert page.worker is not None
    deadline = time.monotonic() + 3
    while page.worker is not None and time.monotonic() < deadline:
        app.processEvents(QEventLoop.AllEvents); time.sleep(.01)
    assert page.worker is None
    assert "Offline test" in page.status.text() and "cached" in page.status.text()
    assert page.list.count() == 1
    window.close(); app.processEvents()


def test_github_installer_missing_git_and_foreign_destination(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("github_installer", Path(__file__).parents[1] / "install-from-github.py")
    installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Git is not installed"):
        installer.main(["--directory", str(tmp_path / "checkout"), "--clone-only"])
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/" + name)
    existing = tmp_path / "checkout"; existing.mkdir(); (existing / "mine.txt").write_text("keep")
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        installer.main(["--directory", str(existing), "--clone-only"])
    assert (existing / "mine.txt").read_text() == "keep"


def test_git_timeout_and_cancellation_stop_the_private_process(manager, tmp_path, monkeypatch):
    fake_git = tmp_path / "fake-git"
    fake_git.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
    fake_git.chmod(0o755)
    monkeypatch.setattr("backend.store.shutil.which", lambda name: str(fake_git) if name == "git" else None)
    store = Store(manager.paths)
    with pytest.raises(SafetyError, match="timed out"):
        store.git("version", timeout=.1)
    errors = []
    def request():
        try: store.git("version")
        except SafetyError as error: errors.append(str(error))
    worker = threading.Thread(target=request)
    worker.start()
    store.cancelled.set()
    worker.join(2)
    assert not worker.is_alive() and errors == ["Repository check cancelled"]


def test_bootstrap_clone_only_and_fast_forward_without_running_installer(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("github_installer", Path(__file__).parents[1] / "install-from-github.py")
    installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
    destination = tmp_path / "source checkout"
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert command[0].endswith("git"), "Clone-only must not execute the manager installer"
        if "clone" in command:
            (destination / ".git").mkdir(parents=True)
            manager = destination / "caelestia-dev-manager/scripts"
            manager.mkdir(parents=True)
            (manager / "install_manager.py").write_text("raise RuntimeError('must not execute')\n")
        output = ""
        if "get-url" in command: output = installer.REPOSITORY
        if "--show-current" in command: output = "main"
        if "rev-parse" in command: output = COMMIT
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(installer.subprocess, "run", run)
    installer.main(["--directory", str(destination), "--clone-only"])
    assert any("clone" in c for c in calls)
    calls.clear()
    installer.main(["--directory", str(destination), "--clone-only"])
    assert any("fetch" in c for c in calls) and any("--ff-only" in c for c in calls)


def test_async_success_uses_main_thread_registry_and_keeps_cache(manager, app_files, monkeypatch):
    app = QApplication.instance() or QApplication([])
    m, files = app_files
    catalog = {"repository": DEFAULT_REPOSITORY, "branch": "main", "commit": COMMIT,
               "checked_at": "test", "entries": [{"manifest": m, "files": files, "hash": source_hash(files)}], "issues": []}
    monkeypatch.setattr(Store, "scan", lambda self: catalog)
    window = Window(manager)
    window.store_page.check()
    deadline = time.monotonic() + 3
    while window.store_page.worker is not None and time.monotonic() < deadline:
        app.processEvents(QEventLoop.AllEvents); time.sleep(.01)
    assert window.store_page.catalog == catalog and window.store_page.list.count() == 1
    assert window.store_page.worker is None
    window.close(); app.processEvents()
