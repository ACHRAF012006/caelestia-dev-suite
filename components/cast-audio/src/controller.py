"""Async state machine. UI talks only over this process's inherited stdin/stdout."""
import asyncio
import time

import audio
from cast import Cast, route, merge_devices
from safety import Failure, text
from stream import Stream
from hls import HlsStream


class Controller:
    def __init__(self, preferences, processes, emit):
        self.prefs, self.processes, self.emit = preferences, processes, emit
        self.cast = Cast(processes)
        self.devices, self.sources = merge_devices([], preferences.values["manual_devices"]), []
        self.receiver = self.stream = self.source = None
        self.operation = self.discovery = self.monitor = None
        self.state, self.message = "Off", preferences.notice or "Not connected"
        self.scanning = False
        self.volume, self.muted = 0, False
        self.visible = True
        self.closing = False
        self.last_scan = -10
        self.auto_pending = preferences.values["reconnect"]

    def publish(self):
        self.emit(self.snapshot())

    def snapshot(self):
        return {"state": self.state, "message": self.message, "scanning": self.scanning,
                   "devices": self.devices, "sources": self.sources,
                   "receiver": self.receiver["name"] if self.receiver else "",
                   "source_name": self.source["name"] if self.source else "",
                   "volume": self.volume, "muted": self.muted, "settings": self.prefs.values}

    def status(self, state, message):
        self.state, self.message = state, message
        self.publish()

    def refresh(self):
        if (self.closing or self.state not in ("Off", "Error") or
                (self.discovery and not self.discovery.done()) or time.monotonic() - self.last_scan < 10):
            return
        self.last_scan = time.monotonic()
        self.discovery = asyncio.create_task(self.discover())

    async def discover(self):
        # A queued idle refresh may run after Start has already taken over.
        if self.closing or self.state not in ("Off", "Error"):
            return
        self.scanning = True
        sources_ready = False
        self.publish()
        try:
            self.sources = await audio.sources(self.processes)
            sources_ready = True
            self.devices = merge_devices(await self.cast.scan(self.prefs.values["discovery_timeout"]), self.prefs.values["manual_devices"])
            if self.state == "Off":
                self.message = "Choose a receiver" if self.devices else "No Cast devices found; check mDNS, firewall and Wi-Fi isolation"
            if self.auto_pending:
                self.auto_pending = False
                target = next((d for d in self.devices if d["id"] == self.prefs.values["last"] and d["supported"]), None)
                if target and self.state == "Off":
                    self.begin(target["id"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.devices = merge_devices([], self.prefs.values["manual_devices"])
            if self.state == "Off":
                if self.devices and sources_ready:
                    self.message = "Local discovery unavailable; choose a saved IP receiver"
                else:
                    self.state, self.message = "Error", self.error(exc)
        finally:
            self.scanning = False
            self.publish()

    @staticmethod
    def error(exc):
        if isinstance(exc, Failure):
            return text(exc, 240)
        if isinstance(exc, TimeoutError):
            return "Connection timed out; check the receiver and network"
        return "Operation failed; check dependencies, audio server and network availability"

    def launch(self, coroutine):
        if self.operation and not self.operation.done():
            coroutine.close()
            return
        self.operation = asyncio.create_task(coroutine)

    def begin(self, identity):
        if self.state not in ("Off", "Error") or self.closing:
            return
        receiver = next((d for d in self.devices if d["id"] == identity and d["supported"]), None)
        if not receiver:
            self.status("Error", "Receiver unavailable; refresh devices")
            return
        self.launch(self.start(receiver))

    async def start(self, receiver):
        self.receiver = receiver
        self.scanning = False
        self.status("Connecting…", "Checking receiver and output monitor…")
        try:
            async with asyncio.timeout(60):
                # Discovery owns a separate catt child. Stop and reap it before
                # capturing; opening the menu must not scan during playback.
                discovery, self.discovery = self.discovery, None
                if discovery and not discovery.done():
                    discovery.cancel()
                    await asyncio.gather(discovery, return_exceptions=True)
                self.sources = await audio.sources(self.processes)
                self.source = audio.select(self.sources, self.prefs.values["source"])
                # Check before capturing; Cast.start checks again before loading.
                if self.cast.busy(await self.cast.info(receiver)):
                    raise Failure("Receiver already busy; stop its current session before casting")
                stream_type = HlsStream if self.prefs.values["format"] == "hls" else Stream
                self.stream = stream_type(self.processes, route(receiver["host"]), receiver["host"], self.prefs.values["stream_port"])
                await self.stream.start(self.source["monitor"], self.prefs.values["bitrate"])
                self.status("Connecting…", "Waiting for receiver playback…")
                await self.cast.start(receiver, self.stream.url)
                # Receivers can still be buffering after eight status polls.
                # Retain the overall deadline rather than abandoning live audio.
                while True:
                    info = await self.cast.info(receiver)
                    if (info.get("content_id") == self.stream.url and info.get("player_state") == "PLAYING"
                            and self.stream.receiver_reads > 0):
                        break
                    if info.get("content_id") == self.stream.url and info.get("idle_reason") == "ERROR":
                        raise Failure("Receiver rejected the audio stream. Check receiver network/media access; its Cast connection is working.")
                    await asyncio.sleep(1)
                if self.prefs.values["remember"]:
                    self.prefs.save({"last": receiver["id"]})
                self.update_volume(info)
                self.status("Casting", self.stream.label)
                self.monitor = asyncio.create_task(self.watch())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            message = self.error(exc)
            if isinstance(exc, TimeoutError) and self.stream and self.stream.receiver_reads:
                message = "Speaker received audio but did not finish buffering within 60 seconds"
            if (self.stream and self.stream.url and not self.stream.failure and not self.stream.receiver_reads
                    and (isinstance(exc, TimeoutError) or "timed out" in message or "did not begin playback" in message)):
                message = (f"Speaker did not request audio from {self.stream.address}:{self.stream.port}. "
                           "Cast control connected, but media loading failed. Check receiver media access and speaker-to-PC TCP routing.")
            await self.cleanup()
            self.status("Error", message)

    def update_volume(self, info):
        value = info.get("volume_level", 0)
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            self.volume = round(value * 100)
        self.muted = info.get("volume_muted") is True

    async def watch(self):
        try:
            tick = 0
            while self.stream:
                await asyncio.sleep(1)
                if self.stream.failure or time.monotonic() - self.stream.last_audio > 10:
                    raise Failure(self.stream.failure or "Stream failed: audio capture stalled")
                try:
                    address = route(self.receiver["host"])
                except OSError:
                    raise Failure("Network changed or receiver route unavailable") from None
                if address != self.stream.address:
                    raise Failure("Network changed; reconnect on the current network")
                tick += 1
                if tick % 10:
                    continue
                info = await self.cast.info(self.receiver)
                if info.get("content_id") != self.stream.url or info.get("player_state") not in ("PLAYING", "BUFFERING"):
                    raise Failure("Cast session ended or was replaced by another controller")
                self.sources = await audio.sources(self.processes)
                current = audio.select(self.sources, self.prefs.values["source"])
                if current["monitor"] != self.source["monitor"]:
                    raise Failure("Audio output changed; reconnect to capture the new output")
                self.update_volume(info)
                self.publish()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.operation and not self.operation.done():
                self.operation.cancel()
                await asyncio.gather(self.operation, return_exceptions=True)
            await self.cleanup()
            self.status("Error", self.error(exc))

    async def cleanup(self):
        stream, receiver = self.stream, self.receiver
        self.stream = self.receiver = self.source = None
        async def stop_receiver():
            if not receiver:
                return True
            try:
                async with asyncio.timeout(5):
                    await self.cast.stop_owned(receiver, stream.url)
                return True
            except Exception:
                return False
        if stream:
            # Issue the remote command while its media is still active. Local
            # capture/HTTP cleanup never waits for a remote status round trip.
            remote = asyncio.create_task(stop_receiver())
            try:
                await stream.close()
                return await remote
            finally:
                if not remote.done():
                    remote.cancel()
                await asyncio.gather(remote, return_exceptions=True)
        return True

    async def stop(self):
        self.auto_pending = False
        self.status("Stopping…", "Stopping capture and disconnecting receiver…")
        for task in (self.operation, self.monitor):
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.operation = self.monitor = None
        confirmed = await self.cleanup()
        self.status("Off", "Not connected" if confirmed else "Audio stopped locally; receiver did not confirm Stop")

    async def control(self, action, value):
        try:
            if not self.stream or self.state != "Casting":
                return
            if (await self.cast.info(self.receiver)).get("content_id") != self.stream.url:
                raise Failure("Cast session ended")
            if action == "volume" and type(value) is int and 0 <= value <= 100:
                await self.cast.command(self.receiver, "volume", str(value))
            elif action == "mute" and type(value) is bool:
                await self.cast.command(self.receiver, "volumemute", "true" if value else "false")
            else:
                raise Failure("Invalid receiver control")
            self.update_volume(await self.cast.info(self.receiver))
            self.publish()
        except Exception as exc:
            self.message = self.error(exc)
            self.publish()

    async def handle(self, message):
        action = message.get("action")
        if action == "refresh":
            self.refresh()
        elif action == "start":
            self.begin(message.get("id"))
        elif action == "stop":
            await self.stop()
        elif action in ("volume", "mute"):
            self.launch(self.control(action, message.get("value")))
        elif action == "visible":
            self.visible = message.get("value") is True
            if self.visible:
                self.refresh()
        elif action == "settings":
            changes = message.get("values")
            try:
                if self.state not in ("Off", "Error"):
                    raise Failure("Stop casting before changing settings")
                if not isinstance(changes, dict) or set(changes) - {"source", "format", "bitrate", "remember", "reconnect", "discovery_timeout", "manual_devices", "stream_port"}:
                    raise Failure("Invalid settings")
                self.prefs.save(changes)
                self.devices = merge_devices([device for device in self.devices if not device.get("manual")], self.prefs.values["manual_devices"])
                self.auto_pending = False
                self.message = "Settings saved"
                self.publish()
            except Exception as exc:
                self.message = self.error(exc)
                self.publish()

    async def close(self):
        self.closing = True
        if self.discovery:
            self.discovery.cancel()
            await asyncio.gather(self.discovery, return_exceptions=True)
        await self.stop()
        await self.processes.close()
