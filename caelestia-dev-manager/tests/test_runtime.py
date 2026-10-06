import json
import os
import subprocess
import time

def test_stop_matches_runtime_and_entrypoint_not_unrelated_arguments(manager, app_files):
    m, files = app_files
    files["src/main.py"] = "import time\ntime.sleep(15)\n"
    manager.create(files); manager.install(m["id"])
    record = manager.installed(m["id"])
    pid = manager.runtime.launch(record)
    # Same interpreter, but an unrelated program merely mentioning an installed file.
    unrelated = subprocess.Popen(["python3", "-c", "import time; time.sleep(15)", str(manager.paths.root(m) / "src/main.py")])
    try:
        deadline = time.monotonic() + 3
        while pid not in manager.runtime.processes(record) and time.monotonic() < deadline: time.sleep(0.05)
        pids = manager.runtime.processes(record)
        assert pid in pids and unrelated.pid not in pids
        manager.runtime.stop(record)
        os.waitpid(pid, 0)
        assert unrelated.poll() is None
    finally:
        unrelated.terminate(); unrelated.wait(timeout=3)
        try: os.kill(pid, 15)
        except ProcessLookupError: pass
