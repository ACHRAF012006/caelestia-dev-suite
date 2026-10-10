import os
import json
import time
import uuid
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
        if record['installed_manifest']['type'] not in {'standalone-app', 'script'}: return []
        expected = self.expectation(record)
        result = []
        for p in Path("/proc").iterdir():
            if not p.name.isdigit(): continue
            if self._identity(int(p.name), expected): result.append(int(p.name))
        return result

    def expectation(self, record):
        from backend.installers import installer
        m = record['installed_manifest']
        if m['type'] not in {'standalone-app', 'script'}: return None
        expected = installer(self.paths, m).command(m)
        entry = str(self.paths.root(m) / m['entrypoint'])
        return ([x.encode() for x in expected[1:expected.index(entry) + 1]], Path(expected[0]).resolve())

    def identity(self, pid, record):
        """Fresh user/executable/argument/start-time identity, never a name match."""
        return self._identity(pid, self.expectation(record))

    def _identity(self, pid, expected):
        if expected is None: return None
        prefix, interpreter = expected
        path = Path('/proc') / str(pid)
        try:
            if path.stat().st_uid != os.getuid(): return None
            # stat comm can contain spaces/parentheses. Fields after its final
            # closing parenthesis begin with field 3; starttime is field 22.
            start = (path / 'stat').read_text().rpartition(')')[2].split()[19]
            args = (path / 'cmdline').read_bytes().split(b'\0')
            executable = (path / 'exe').resolve()
            if args[1:1 + len(prefix)] != prefix or executable != interpreter: return None
            return (pid, start, str(executable))
        except (OSError, IndexError): return None

    def launch_path(self, record):
        from backend.paths import component_id
        return no_symlinks(self.paths.state / 'caelestia-dev-manager/runtime' / (component_id(record['id']) + '.json'))

    def launch_records(self, record):
        path = self.launch_path(record)
        try:
            if not path.is_file() or path.stat().st_size > 65536: return []
            value = json.loads(path.read_text())
            if value['component'] != record['id'] or value['format'] != 1 or len(value['launches']) > 32: return []
            return value['launches']
        except (OSError, ValueError, KeyError, TypeError): return []

    def app_state(self, record, pids=None):
        if pids is None: pids = self.processes(record)
        if pids: return 'Running'
        for launch in self.launch_records(record):
            try:
                boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                path = Path('/proc') / str(launch['pid'])
                start = (path / 'stat').read_text().rpartition(')')[2].split()[19]
                if launch['boot'] == boot and launch['start'] == start and path.stat().st_uid == os.getuid():
                    return 'Starting' if time.time() - launch['time'] < 5 else 'Process ownership cannot be verified'
            except (OSError, ValueError, KeyError, TypeError, IndexError): continue
        return 'Stopped'

    def verify_launch(self, record):
        from backend.installers import installer
        m = record['installed_manifest']
        if not record.get('installed'): raise SafetyError('Component is not installed')
        adapter = installer(self.paths, m)
        if m['type'] == 'user-service':
            path = no_symlinks(self.paths.config / 'systemd/user' / self.unit(record['id']))
            expected = adapter.unit(m)
            mode = 0o644
        elif m['type'] in {'standalone-app', 'script'}:
            path = no_symlinks(self.paths.bin / record['id'])
            expected = adapter.launcher(m)
            mode = 0o755
        else: raise SafetyError('This component runs in the real Caelestia environment; use its reviewed activation')
        if not path.is_file() or path.read_bytes() != expected or path.stat().st_mode & 0o7777 != mode:
            raise SafetyError('Generated runtime entry changed; revalidate/repair through Install / Update before launching')
        entry = no_symlinks(self.paths.root(m) / m['entrypoint'])
        if not entry.is_file(): raise SafetyError('Installed entrypoint is missing or not a regular file')
        if m.get('dependencies', {}).get('python'):
            if not no_symlinks(self.paths.root(m) / '_venv/bin/python').is_file(): raise SafetyError('Private Python interpreter is missing')

    def launch(self, record):
        if record.get('installed_manifest', {}).get('type') in {'standalone-app', 'script'} and not record.get('enabled'):
            raise SafetyError('Enable the component before launching')
        self.verify_launch(record)
        m = record["installed_manifest"]
        if m["type"] == "user-service": return self.systemctl("start", self.unit(record["id"]))
        if not record.get("enabled"): raise SafetyError("Enable the component before launching")
        log = no_symlinks(self.paths.state / "caelestia-dev-manager/logs" / (record["id"] + ".log"))
        if log.exists() and not log.is_file(): raise SafetyError("Runtime log must be a regular file")
        log.parent.mkdir(parents=True, exist_ok=True)
        # A new session, closed descriptors and no Qt-owned QProcess allow survival of manager exit.
        with log.open("ab") as out:
            token = uuid.uuid4().hex
            p = subprocess.Popen([str(self.paths.bin / record["id"])], stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=out, start_new_session=True, close_fds=True,
                                 env={**os.environ, 'CDM_LAUNCH_TOKEN': token})
        try:
            start = (Path('/proc') / str(p.pid) / 'stat').read_text().rpartition(')')[2].split()[19]
            launch = {'pid': p.pid, 'start': start, 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                      'token': token, 'time': time.time()}
            atomic_write(self.launch_path(record), json.dumps({'format': 1, 'component': record['id'],
                         'launches': (self.launch_records(record) + [launch])[-32:]}).encode(), 0o600)
        except (OSError, IndexError): pass  # Very short-lived commands need no tracking receipt.
        return p.pid

    def stop(self, record):
        if record["installed_manifest"]["type"] == "user-service": return self.systemctl("stop", self.unit(record["id"]))
        for pid in self.processes(record):
            identity = self.identity(pid, record)
            if identity is None: continue
            if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
                raise SafetyError('Process ownership cannot be verified safely on this kernel; close the application directly')
            fd = None
            try:
                fd = os.pidfd_open(pid)
                if self.identity(pid, record) == identity:
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
            except ProcessLookupError: pass
            finally:
                if fd is not None: os.close(fd)

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
