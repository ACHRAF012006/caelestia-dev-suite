"""A bounded settings-only Unix endpoint, private to the current Linux user."""
import asyncio
import json
import os
import socket
import stat
import struct

from safety import Failure, no_links


class SettingsServer:
    def __init__(self, preferences, controller, dispatch):
        self.path = no_links(preferences.runtime / "settings.sock")
        self.controller, self.dispatch = controller, dispatch
        self.server = None
        self.tasks = set()

    async def start(self):
        if self.path.exists():
            info = self.path.stat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise Failure("Settings endpoint is not an owned Unix socket")
            self.path.unlink()  # The helper's private flock already establishes sole ownership.
        self.server = await asyncio.start_unix_server(self.client, path=str(self.path), limit=16384)
        self.path.chmod(0o600)

    async def client(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            credentials = writer.get_extra_info("socket").getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            if struct.unpack("3i", credentials)[1] != os.getuid():
                return
            async with asyncio.timeout(3):
                request = json.loads(await reader.readline())
                if not isinstance(request, dict) or request.get("action") not in {"get", "settings"}:
                    raise Failure("Only settings requests are accepted")
                if request["action"] == "settings":
                    if self.controller.state not in ("Off", "Error"):
                        raise Failure("Stop casting before changing settings")
                    # Validate before dispatch so callers receive an explicit failure.
                    changes = request.get("values")
                    if not isinstance(changes, dict) or set(changes) - {"source", "bitrate", "remember", "reconnect", "discovery_timeout", "manual_devices", "stream_port"}:
                        raise Failure("Invalid settings")
                    expected = self.controller.prefs.validate({**self.controller.prefs.values, **changes})
                    await self.dispatch(request)
                    if self.controller.prefs.values != expected:
                        raise Failure(self.controller.message)
                response = {"ok": True, "snapshot": self.controller.snapshot()}
        except (ValueError, OSError, TimeoutError, Failure) as error:
            response = {"ok": False, "error": str(error)[:240]}
        except asyncio.CancelledError:
            raise
        finally:
            if 'response' in locals():
                writer.write(json.dumps(response).encode() + b"\n")
                try:
                    await writer.drain()
                except (OSError, ConnectionError):
                    pass
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass
            finally:
                self.tasks.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        if self.path.exists() and stat.S_ISSOCK(self.path.stat().st_mode):
            self.path.unlink()
