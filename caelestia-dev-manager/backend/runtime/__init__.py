import os
from pathlib import Path
import signal
import subprocess
from backend.paths import SafetyError, atomic_write, no_symlinks

class Runtime:
    def __init__(self, paths, real=True):
        self.paths, self.real = paths, real
        self.calls = []

    def systemctl(self, *args):
        self.calls.append(list(args))
        if not self.real: return "active" if args[0] == "is-active" else ""
        r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=15)
        if r.returncode and args[0] not in {"is-active", "is-enabled", "show"}:
            # Broken or already absent units must remain uninstallable. Never ignore stop errors on active units.
            if args[0] in {"stop", "disable"}:
                load = self.systemctl("show", args[-1], "--property=LoadState", "--value")
                active = self.systemctl("is-active", args[-1])
                if load in {"not-found", "bad-setting", "error"} and active not in {"active", "activating", "deactivating", "reloading"}:
                    return r.stdout.strip()
            raise SafetyError(r.stderr.strip() or "systemctl failed")
        return r.stdout.strip()

    def unit(self, id): return "cdm-" + id + ".service"

    def refresh_desktop(self):
        import shutil
        if self.real and shutil.which("kbuildsycoca6"):
            subprocess.run(["kbuildsycoca6", "--noincremental"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)

    def processes(self, record):
        if not record.get("installed"): return []
        from backend.installers import installer
        manifest = record["installed_manifest"]
        if manifest["type"] not in {"standalone-app", "script"}: return []
        expected = installer(self.paths, manifest).command(manifest)
        entrypoint = str(self.paths.root(manifest) / manifest["entrypoint"])
        prefix = [x.encode() for x in expected[1:expected.index(entrypoint) + 1]]
        interpreter = Path(expected[0]).resolve()
        result = []
        for p in Path("/proc").iterdir():
            if not p.name.isdigit(): continue
            try:
                if p.stat().st_uid != os.getuid(): continue
                args = (p / "cmdline").read_bytes().split(b"\0")
                if args[1:1 + len(prefix)] == prefix and (p / "exe").resolve() == interpreter:
                    result.append(int(p.name))
            except OSError: pass
        return result

    def launch(self, record):
        m = record["installed_manifest"]
        if m["type"] == "user-service": return self.systemctl("start", self.unit(record["id"]))
        if not record.get("enabled"): raise SafetyError("Enable the component before launching")
        log = no_symlinks(self.paths.state / "caelestia-dev-manager/logs" / (record["id"] + ".log"))
        log.parent.mkdir(parents=True, exist_ok=True)
        # A new session, closed descriptors and no Qt-owned QProcess allow survival of manager exit.
        with log.open("ab") as out:
            p = subprocess.Popen([str(self.paths.bin / record["id"])], stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=out, start_new_session=True, close_fds=True)
        return p.pid

    def stop(self, record):
        if record["installed_manifest"]["type"] == "user-service": return self.systemctl("stop", self.unit(record["id"]))
        for pid in self.processes(record):
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass

    def logs(self, record):
        type = record.get("installed_manifest", record["manifest"])["type"]
        if type in {"user-service", "caelestia-plugin", "qml-component"}:
            unit = self.unit(record["id"]) if type == "user-service" else "caelestia-shell.service"
            if not self.real: return "Test runtime: no journal"
            return subprocess.run(["journalctl", "--user", "-u", unit, "-n", "100", "--no-pager"], capture_output=True, text=True, timeout=8).stdout
        path = no_symlinks(self.paths.state / "caelestia-dev-manager/logs" / (record["id"] + ".log"))
        if not path.exists(): return "No logs recorded"
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 128_000))
            return stream.read().decode(errors="replace")
