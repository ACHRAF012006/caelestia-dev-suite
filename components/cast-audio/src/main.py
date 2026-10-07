"""One supervised helper per user, with bounded JSON-lines IPC and clean shutdown."""
import asyncio
import fcntl
import json
import os
import signal
import sys

from child import guard
from controller import Controller
from processes import Processes
from safety import Preferences, no_links
from settings_ipc import SettingsServer


def emit(value):
    try:
        print(json.dumps(value, ensure_ascii=True, allow_nan=False), flush=True)
    except (BrokenPipeError, OSError):
        pass


async def main():
    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        loop.add_signal_handler(sig, shutdown.set)
    guard(os.getppid())
    prefs = Preferences()
    path = no_links(prefs.runtime / "helper.lock")
    with open(path, "a", encoding="utf-8") as lock:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            emit({"state": "Error", "message": "Cast Audio is already running in another shell instance"})
            return
        processes = Processes(prefs)
        controller = Controller(prefs, processes, emit)
        command_lock = asyncio.Lock()
        async def dispatch(message):
            async with command_lock:
                await controller.handle(message)
        settings_server = SettingsServer(prefs, controller, dispatch)
        await settings_server.start()
        reader = asyncio.StreamReader(limit=16384)
        transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

        async def commands():
            try:
                while raw := await reader.readline():
                    value = json.loads(raw)
                    if not isinstance(value, dict):
                        continue
                    if value.get("action") == "quit":
                        break
                    await dispatch(value)
            except (ValueError, OSError):
                pass
            finally:
                shutdown.set()

        async def refresh():
            while True:
                await asyncio.sleep(90)
                if controller.visible and controller.state in ("Off", "Error"):
                    controller.refresh()

        controller.publish()
        controller.refresh()
        tasks = [asyncio.create_task(commands()), asyncio.create_task(refresh())]
        try:
            await shutdown.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await settings_server.close()
            await controller.close()
            transport.close()


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        emit({"state": "Error", "message": "Python 3.11 or newer is required"})
        sys.exit(1)
    try:
        asyncio.run(main())
    except Exception:
        emit({"state": "Error", "message": "Helper could not start; check private XDG paths and required dependencies"})
        sys.exit(1)
