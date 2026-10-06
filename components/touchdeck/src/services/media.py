"""Asynchronous D-Bus worker; known MPRIS and login1 interfaces only."""
import asyncio
import copy
import logging
import os
import threading
import time
from PySide6.QtCore import QObject, Signal

PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"


def plain(value):
    if hasattr(value, "value"):
        return plain(value.value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


class Media(QObject):
    changed = Signal(dict)
    completed = Signal(str, bool, str)

    def __init__(self):
        super().__init__()
        self.state = {"players": {}, "error": ""}
        self.changed.connect(self._receive)
        self.loop = None
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="touchdeck-dbus")
        self.thread.start()

    def _receive(self, state):
        if bool(state.get("error")) != bool(self.state.get("error")):
            logging.getLogger("touchdeck").info("MPRIS unavailable" if state.get("error") else "MPRIS connected")
        self.state = state

    def close(self):
        self.stopped.set()

    def request(self, kind, value, token=""):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._request(kind, value, token), self.loop)
        else:
            self.completed.emit(token, False, "D-Bus unavailable")

    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception:
            self.changed.emit({"players": {}, "error": "MPRIS unavailable: check session D-Bus and dbus-next"})

    async def _call(self, bus, destination, path, interface, member, signature="", body=None):
        from dbus_next import Message, MessageType
        reply = await asyncio.wait_for(bus.call(Message(destination=destination, path=path, interface=interface,
                                                         member=member, signature=signature, body=body or [])), 3)
        if reply.message_type == MessageType.ERROR:
            raise ValueError(reply.error_name)
        return plain(reply.body)

    async def _main(self):
        from dbus_next.aio import MessageBus
        self.loop = asyncio.get_running_loop()
        self.bus = await MessageBus().connect()
        self.system_bus = None
        self.players = {}
        self.dirty = True
        async def match(rule):
            await self._call(self.bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "AddMatch", "s", [rule])
        self.bus.add_message_handler(self._message)
        for rule in ("type='signal',interface='org.freedesktop.DBus',member='NameOwnerChanged'",
                     "type='signal',path='/org/mpris/MediaPlayer2'"):
            await match(rule)
        last = 0.0
        try:
            while not self.stopped.is_set():
                if self.dirty or time.monotonic() - last >= 5:
                    self.dirty = False
                    await self._refresh()
                    last = time.monotonic()
                await asyncio.sleep(0.25)
        finally:
            self.bus.disconnect()
            if self.system_bus:
                self.system_bus.disconnect()

    def _message(self, message):
        from dbus_next import MessageType
        if message.message_type == MessageType.SIGNAL:
            if message.member == "NameOwnerChanged" and message.body and str(message.body[0]).startswith("org.mpris.MediaPlayer2."):
                self.dirty = True
            elif message.path == PATH:
                self.dirty = True

    async def _refresh(self):
        try:
            names = (await self._call(self.bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames"))[0]
            async def fetch(name):
                try:
                    props = (await self._call(self.bus, name, PATH, PROPS, "GetAll", "s", [PLAYER]))[0]
                    identity = (await self._call(self.bus, name, PATH, PROPS, "Get", "ss", ["org.mpris.MediaPlayer2", "Identity"]))[0]
                    props["identity"], props["sampled"] = identity, time.monotonic()
                    return name, props
                except Exception:
                    return name, None
            pairs = await asyncio.gather(*(fetch(n) for n in names if n.startswith("org.mpris.MediaPlayer2.")))
            self.players = {n: p for n, p in pairs if p is not None}
            self.changed.emit({"players": copy.deepcopy(self.players), "error": ""})
        except Exception:
            self.changed.emit({"players": {}, "error": "Session D-Bus unavailable"})

    async def _request(self, kind, value, token):
        try:
            if kind == "power":
                from dbus_next.aio import MessageBus
                from dbus_next.constants import BusType
                if not self.system_bus:
                    self.system_bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
                dest, path, interface = "org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager"
                if value in ("lock", "logout"):
                    session = os.environ.get("XDG_SESSION_ID")
                    if not session:
                        session_path = (await self._call(self.system_bus, dest, path, interface, "GetSessionByPID", "u", [os.getpid()]))[0]
                        session = (await self._call(self.system_bus, dest, session_path, PROPS, "Get", "ss", ["org.freedesktop.login1.Session", "Id"]))[0]
                    await self._call(self.system_bus, dest, path, interface, "LockSession" if value == "lock" else "TerminateSession", "s", [session])
                else:
                    member = {"suspend": "Suspend", "reboot": "Reboot", "shutdown": "PowerOff"}[value]
                    await self._call(self.system_bus, dest, path, interface, member, "b", [False])
                message = "Session action requested"
            else:
                name, method = value["player"], value["method"]
                if name not in self.players:
                    raise ValueError("Player disappeared")
                props = self.players[name]
                if method == "SetPosition":
                    track = props.get("Metadata", {}).get("mpris:trackid", "")
                    if not props.get("CanSeek") or not track or track.endswith("/NoTrack"):
                        raise ValueError("Seeking unsupported")
                    await self._call(self.bus, name, PATH, PLAYER, method, "ox", [track, int(value["position"])])
                else:
                    if method not in ("Previous", "Play", "Pause", "PlayPause", "Stop", "Next"):
                        raise ValueError("Unknown media action")
                    await self._call(self.bus, name, PATH, PLAYER, method)
                self.dirty = True
                message = "Media action sent"
            self.completed.emit(token, True, message)
        except Exception:
            self.completed.emit(token, False, "Action unavailable, denied by session policy, or unsupported by player")

    def selected(self, config):
        players = self.state["players"]
        chosen = config.get("player", "")
        if config.get("auto_player", True):
            chosen = next((name for name, p in players.items() if p.get("PlaybackStatus") == "Playing"), next(iter(players), ""))
        return chosen, players.get(chosen, {})
