import shutil
import socket
import subprocess
import threading
import time
from PySide6.QtCore import QObject, Signal


class Monitor(QObject):
    changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.state = {}
        self.changed.connect(self._receive)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="touchdeck-monitor")
        self.thread.start()

    def _receive(self, state):
        self.state = state

    def close(self):
        self.stop_event.set()

    def _run(self):
        try:
            import psutil
        except ImportError:
            self.changed.emit({"error": "Monitoring unavailable: psutil missing"})
            return
        previous, stamp = psutil.net_io_counters(), time.monotonic()
        slow, tick = {}, 0
        psutil.cpu_percent()
        while not self.stop_event.wait(1):
            try:
                now, net = time.monotonic(), psutil.net_io_counters()
                memory = psutil.virtual_memory()
                state = {"cpu": psutil.cpu_percent(), "ram": memory.percent,
                         "upload": max(0, net.bytes_sent - previous.bytes_sent) / (now - stamp),
                         "download": max(0, net.bytes_recv - previous.bytes_recv) / (now - stamp),
                         "uptime": (time.time() - psutil.boot_time()) / 3600}
                previous, stamp = net, now
                if tick % 2 == 0:
                    try:
                        temperatures = psutil.sensors_temperatures()
                        entries = temperatures.get("coretemp", []) or temperatures.get("k10temp", [])
                        slow["temperature"] = max((x.current for x in entries), default=None)
                    except (OSError, AttributeError):
                        slow["temperature"] = None
                    if shutil.which("nvidia-smi"):
                        try:
                            result = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                                                    capture_output=True, text=True, timeout=1, check=True)
                            values = [float(x.strip()) for x in result.stdout.splitlines()[0].split(",")]
                            slow["gpu"] = "GPU %.0f%% · %.0f°C · %.0f/%.0f MiB" % tuple(values)
                        except (OSError, ValueError, subprocess.SubprocessError, IndexError):
                            slow["gpu"] = "GPU monitoring unavailable"
                if tick % 5 == 0:
                    slow["disk"] = psutil.disk_usage(str(__import__("pathlib").Path.home())).percent
                    addresses = psutil.net_if_addrs()
                    active = psutil.net_if_stats()
                    slow["ip"] = ", ".join(x.address for name, entries in addresses.items() if name != "lo" and active.get(name) and active[name].isup
                                          for x in entries if x.family == socket.AF_INET) or "Offline"
                    slow["connection"] = "Network status"
                    if shutil.which("nmcli"):
                        try:
                            result = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"], capture_output=True, text=True, timeout=1)
                            if result.returncode == 0:
                                slow["connection"] = result.stdout.strip().replace("\n", " · ") or "Disconnected"
                        except (OSError, subprocess.SubprocessError):
                            pass
                tick += 1
                self.changed.emit({**state, **slow})
            except (OSError, ValueError):
                self.changed.emit({"error": "Some system metrics are unavailable"})
