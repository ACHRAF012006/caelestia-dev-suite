"""Run: python3 -B -m unittest discover -s tests -v. No receiver is contacted."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import audio
from cast import Cast, devices, merge_devices
from settings_ipc import SettingsServer
from settings_client import request as settings_request
from controller import Controller
from processes import Processes
from safety import Failure, Preferences, local_ip
from stream import Stream
from hls import HlsStream, memory_root, reap_abandoned
from cast_live import checked_url, load as load_live


class TempCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cast-test-")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name + "/config",
                                          "XDG_RUNTIME_DIR": self.temp.name + "/run"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.prefs = Preferences()
        self.processes = Processes(self.prefs)
        self.addAsyncCleanup(self.processes.close)

    async def test_bad_settings_recover_and_do_not_enable_capture(self):
        self.prefs.path.write_text("{broken")
        prefs = Preferences()
        self.assertTrue(prefs.notice)
        self.assertFalse(prefs.values["reconnect"])
        prefs.save({"remember": False, "reconnect": True, "last": "old"})
        self.assertFalse(prefs.values["reconnect"])
        self.assertEqual(prefs.values["last"], "")
        with self.assertRaises(Failure):
            prefs.save({"command": "anything"})

    async def test_live_mode_migrates_old_preferences_and_rejects_other_formats(self):
        self.assertEqual(Preferences.validate({"bitrate": 192})["format"], "hls")
        self.prefs.save({"format": "mp3"})
        self.assertEqual(Preferences().values["format"], "mp3")
        for value in ("wav", [], None):
            with self.assertRaises(Failure):
                self.prefs.save({"format": value})

    async def test_live_sender_only_accepts_private_component_manifest_urls(self):
        valid = "http://192.168.1.2:48200/" + "a" * 48 + "/live.m3u8"
        self.assertEqual(checked_url(valid), valid)
        for value in (valid.replace("192.168.1.2", "8.8.8.8"), valid.replace("http:", "https:"),
                      valid + "?token=other", valid.replace("48200", "80"), valid.replace("live.m3u8", "settings.json"),
                      valid.replace("192.168.1.2", "user@192.168.1.2")):
            with self.assertRaises(Failure):
                checked_url(value)

    async def test_live_sender_can_load_from_backdrop_without_a_media_status_reply(self):
        url = "http://192.168.1.2:48200/" + "a" * 48 + "/live.m3u8"
        cast = MagicMock()
        cast.status.app_id = "E8C28D3C"
        cast.media_controller.status.player_state = "UNKNOWN"
        cast.media_controller.status.content_id = ""
        def accepted(value, *args, **kwargs):
            cast.media_controller.status.content_id = value
        cast.media_controller.play_media.side_effect = accepted
        with patch.dict(sys.modules, {"catt.discovery": SimpleNamespace(get_cast_with_ip=lambda *_: cast)}):
            load_live("192.168.1.5", url)
        cast.media_controller.update_status.assert_not_called()
        cast.media_controller.play_media.assert_called_once_with(url, "application/vnd.apple.mpegurl", title="Caelestia system audio", stream_type="LIVE")
        cast.disconnect.assert_called_once()

    async def test_live_sender_preserves_a_busy_default_receiver(self):
        url = "http://192.168.1.2:48200/" + "a" * 48 + "/live.m3u8"
        cast = MagicMock()
        cast.status.app_id = "CC1AD845"
        cast.media_controller.status.player_state = "PLAYING"
        cast.media_controller.update_status.side_effect = lambda **kwargs: kwargs["callback_function"](True, {})
        with patch.dict(sys.modules, {"catt.discovery": SimpleNamespace(get_cast_with_ip=lambda *_: cast)}):
            with self.assertRaisesRegex(Failure, "busy"):
                load_live("192.168.1.5", url)
        cast.media_controller.play_media.assert_not_called()
        cast.disconnect.assert_called_once()

    async def test_hls_snapshots_bound_history_and_reject_external_playlist_paths(self):
        stream = HlsStream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.directory = Path(self.temp.name) / "segments"
        stream.directory.mkdir()
        folder = stream.directory
        self.addAsyncCleanup(stream.close)
        for index in range(18):
            name = f"segment-{index}.ts"
            (folder/name).write_bytes(b"encoded audio")
            names = [f"segment-{n}.ts" for n in range(max(0, index-5), index+1)]
            (folder/"live.m3u8").write_text("#EXTM3U\n" + "\n".join(names) + "\n")
            stream.read_snapshot()
        self.assertTrue(stream.ready.is_set())
        self.assertEqual(len(stream.segments), 12)
        self.assertNotIn("segment-0.ts", stream.segments)
        previous = stream.playlist
        for name in ("../settings.json", "http://192.168.1.2/private.ts", "segment-999.ts"):
            (folder/"live.m3u8").write_text("#EXTM3U\n" + name + "\n")
            with self.assertRaises((Failure, FileNotFoundError)):
                stream.read_snapshot()
            self.assertEqual(stream.playlist, previous)
        await stream.close()
        self.assertFalse(folder.exists())

    async def test_subsecond_live_playlist_uses_valid_target_and_does_not_reread_unchanged_audio(self):
        stream = HlsStream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.directory = Path(self.temp.name) / "segments"
        stream.directory.mkdir()
        self.addAsyncCleanup(stream.close)
        names = [f"segment-{n}.ts" for n in range(6)]
        for name in names:
            (stream.directory/name).write_bytes(b"encoded audio")
        raw = "#EXTM3U\n#EXT-X-TARGETDURATION:0\n" + "".join(f"#EXTINF:0.5,\n{name}\n" for name in names)
        (stream.directory/"live.m3u8").write_text(raw)
        stream.read_snapshot()
        self.assertIn(b"#EXT-X-TARGETDURATION:1", stream.playlist)
        self.assertTrue(stream.ready.is_set())
        audio_time = stream.last_audio
        # If unchanged snapshots accidentally re-read, these now-missing
        # segments would fail and falsely count as fresh capture.
        stream.segments.clear()
        for name in names:
            (stream.directory/name).unlink()
        stream.read_snapshot()
        self.assertEqual(stream.last_audio, audio_time)

    async def test_hls_http_serves_only_the_current_session_with_finite_responses(self):
        stream = HlsStream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.playlist = b"#EXTM3U\nsegment-1.ts\n"
        stream.segments["segment-1.ts"] = b"encoded audio"
        stream.server = await asyncio.start_server(stream.serve, "127.0.0.1", 0)
        self.addAsyncCleanup(stream.close)
        port = stream.server.sockets[0].getsockname()[1]
        async def fetch(path, method="GET"):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            try:
                writer.write(f"{method} {path} HTTP/1.1\r\nHost: test\r\n\r\n".encode())
                await writer.drain()
                return await asyncio.wait_for(reader.read(), 1)
            finally:
                writer.close(); await writer.wait_closed()
        manifest = await fetch(stream.path)
        self.assertIn(b"application/vnd.apple.mpegurl", manifest)
        self.assertTrue(manifest.endswith(stream.playlist))
        segment = await fetch(stream.prefix + "segment-1.ts")
        self.assertIn(b"video/mp2t", segment)
        self.assertTrue(segment.endswith(b"encoded audio"))
        self.assertEqual(stream.receiver_reads, len(b"encoded audio"))
        self.assertFalse((await fetch(stream.path, "HEAD")).split(b"\r\n\r\n", 1)[1])
        for path in ("/", stream.prefix + "../settings.json", stream.prefix + "segment-999.ts", "/other/segment-1.ts"):
            self.assertIn(b"404", (await fetch(path)).split(b"\r\n",1)[0])
        self.assertIn(b"405", (await fetch(stream.path, "POST")).split(b"\r\n",1)[0])
        stream.receiver, stream.address = "192.168.1.5", "192.168.1.2"
        self.assertIn(b"404", (await fetch(stream.path)).split(b"\r\n",1)[0])

    async def test_hls_never_falls_back_to_a_disk_directory(self):
        with patch("hls.Path.read_text", return_value="1 2 0:3 / /dev/shm rw - ext4 /dev/sda1 rw"):
            with self.assertRaisesRegex(Failure, "tmpfs"):
                memory_root()

    async def test_abandoned_live_buffers_preserve_active_or_unrecognized_files(self):
        root = Path(self.temp.name)
        prefix = f"cast-audio-{os.getuid()}-"
        abandoned = root / (prefix + "99999999-dead")
        abandoned.mkdir(); (abandoned/"segment-1.ts").write_bytes(b"old audio")
        active = root / (prefix + str(os.getpid()) + "-active")
        active.mkdir(); (active/"segment-1.ts").write_bytes(b"current audio")
        unrelated = root / (prefix + "99999999-other")
        unrelated.mkdir(); (unrelated/"keep.txt").write_bytes(b"unowned")
        reap_abandoned(root)
        self.assertFalse(abandoned.exists())
        self.assertTrue((active/"segment-1.ts").exists())
        self.assertTrue((unrelated/"keep.txt").exists())

    async def test_manual_devices_are_persisted_and_deduplicated_with_discovery(self):
        self.prefs.save({"manual_devices": [{"name": "VLAN Speaker", "host": "192.168.20.8"}], "stream_port": 48200})
        restored = Preferences()
        self.assertEqual(restored.values["stream_port"], 48200)
        found = merge_devices([{"id": "discovered", "host": "192.168.20.8", "name": "Other label"}], restored.values["manual_devices"])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "manual:192.168.20.8")
        self.assertEqual(found[0]["name"], "VLAN Speaker")
        with self.assertRaises(Failure):
            self.prefs.save({"manual_devices": [{"name": "Public", "host": "8.8.8.8"}]})
        with self.assertRaises(Failure):
            self.prefs.save({"manual_devices": restored.values["manual_devices"] * 2})
        with self.assertRaises(Failure):
            self.prefs.save({"stream_port": 80})

    async def test_manual_receiver_remains_usable_when_mdns_discovery_fails(self):
        self.prefs.save({"manual_devices": [{"name": "Routed speaker", "host": "10.20.0.8"}]})
        controller = Controller(self.prefs, self.processes, lambda value: None)
        self.assertEqual(controller.devices[0]["host"], "10.20.0.8")
        controller.cast.scan = AsyncMock(side_effect=Failure("mDNS unavailable"))
        with patch("controller.audio.sources", new=AsyncMock(return_value=[])):
            await controller.discover()
        self.assertEqual(controller.devices[0]["id"], "manual:10.20.0.8")
        controller.start = AsyncMock()
        controller.begin("manual:10.20.0.8")
        await controller.operation
        controller.start.assert_awaited_once()

    async def test_connect_cancels_and_reaps_the_running_discovery_child(self):
        controller = Controller(self.prefs, self.processes, lambda value: snapshots.append(value))
        snapshots = []
        entered = asyncio.Event()
        child = None
        async def scan(timeout):
            nonlocal child
            child = await self.processes.spawn([sys.executable, "-c", "import time;time.sleep(30)"])
            entered.set()
            try:
                await child.wait()
            finally:
                await self.processes.end(child)
        controller.cast.scan = scan
        stream = AsyncMock()
        stream.url, stream.receiver_reads = "our-session", 1
        async def capture(*args):
            self.assertFalse(self.processes.children)
            self.assertIsNotNone(child.returncode)
        stream.start.side_effect = capture
        controller.cast.info = AsyncMock(side_effect=[{"app_id": "CC1AD845", "player_state": "IDLE"},
            {"app_id": "CC1AD845", "player_state": "PLAYING", "content_id": stream.url}])
        controller.cast.start = AsyncMock()
        controller.cast.stop_owned = AsyncMock()
        with patch("controller.audio.sources", new=AsyncMock(return_value=[{"id": "output", "name": "Output", "monitor": "output.monitor", "default": True}])), \
             patch("controller.HlsStream", return_value=stream), patch("controller.route", return_value="192.168.1.2"):
            controller.refresh()
            discovery = controller.discovery
            await asyncio.wait_for(entered.wait(), 1)
            self.assertTrue(controller.scanning)
            await controller.start({"id": "receiver", "host": "192.168.1.5", "name": "Speaker"})
            self.assertTrue(discovery.cancelled())
            self.assertIsNone(controller.discovery)
            self.assertEqual(controller.state, "Casting")
            self.assertFalse(controller.scanning)
            self.assertTrue(all(not value["scanning"] for value in snapshots if value["state"] in ("Connecting…", "Casting")))
            await controller.close()

    async def test_visible_and_manual_refresh_never_scan_an_active_session(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.cast.scan = AsyncMock()
        for state in ("Connecting…", "Casting", "Stopping…"):
            controller.state = state
            controller.last_scan = -10
            await controller.handle({"action": "visible", "value": True})
            await controller.handle({"action": "refresh"})
            # Also reject a refresh task queued before the state changed.
            await controller.discover()
            self.assertIsNone(controller.discovery)
            self.assertFalse(controller.scanning)
            self.assertEqual(controller.last_scan, -10)
        controller.cast.scan.assert_not_called()

    async def test_discovery_does_not_hide_playback_failure(self):
        self.prefs.save({"manual_devices": [{"name": "Speaker", "host": "10.20.0.8"}]})
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.state = "Error"
        controller.message = "Speaker did not request audio from 10.20.1.5:48200"
        controller.cast.scan = AsyncMock(side_effect=Failure("mDNS unavailable"))
        with patch("controller.audio.sources", new=AsyncMock(return_value=[])):
            await controller.discover()
        self.assertEqual(controller.state, "Error")
        self.assertIn("48200", controller.message)
        self.assertEqual(controller.devices[0]["host"], "10.20.0.8")
        controller.cast.scan = AsyncMock(return_value=[])
        with patch("controller.audio.sources", new=AsyncMock(return_value=[])):
            await controller.discover()
        self.assertEqual(controller.state, "Error")
        self.assertIn("48200", controller.message)

    async def test_manual_receiver_discovery_failure_is_only_a_notice(self):
        self.prefs.save({"manual_devices": [{"name": "Speaker", "host": "10.20.0.8"}]})
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.cast.scan = AsyncMock(side_effect=Failure("mDNS unavailable"))
        with patch("controller.audio.sources", new=AsyncMock(return_value=[])):
            await controller.discover()
        self.assertEqual(controller.state, "Off")
        self.assertIn("saved IP", controller.message)

    async def test_playback_timeout_reports_actual_return_port_and_closes_capture(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        stream = AsyncMock()
        stream.url = "http://10.20.1.5:48200/private-session/live.mp3"
        stream.address = "10.20.1.5"
        stream.port = 48200
        stream.failure = ""
        stream.receiver_reads = 0
        controller.cast.info = AsyncMock(return_value={"app_id": "CC1AD845", "player_state": "IDLE"})
        controller.cast.start = AsyncMock(side_effect=Failure("catt timed out"))
        controller.cast.stop_owned = AsyncMock()
        with patch("controller.HlsStream", return_value=stream), patch("controller.route", return_value=stream.address), \
             patch("controller.audio.sources", new=AsyncMock(return_value=[{"id": "speaker", "name": "Speaker", "default": True, "monitor": "speaker.monitor"}])):
            await controller.start({"host": "10.20.0.8", "name": "Speaker"})
        self.assertEqual(controller.state, "Error")
        self.assertIn("10.20.1.5:48200", controller.message)
        self.assertNotIn("private-session", controller.message)
        stream.close.assert_awaited_once()
        self.assertIsNone(controller.stream)

    async def test_receiver_rejection_is_reported_without_claiming_a_firewall_cause(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        stream = AsyncMock()
        stream.url = "http://10.20.1.5:48200/private/live.mp3"
        stream.failure = ""
        stream.receiver_reads = 0
        controller.cast.info = AsyncMock(side_effect=[
            {"app_id": "CC1AD845", "player_state": "IDLE"},
            {"app_id": "CC1AD845", "player_state": "IDLE", "content_id": stream.url, "idle_reason": "ERROR"}])
        controller.cast.start = AsyncMock()
        controller.cast.stop_owned = AsyncMock()
        with patch("controller.HlsStream", return_value=stream), patch("controller.route", return_value="10.20.1.5"), \
             patch("controller.audio.sources", new=AsyncMock(return_value=[{"id": "speaker", "name": "Speaker", "default": True, "monitor": "speaker.monitor"}])):
            await controller.start({"host": "10.20.0.8", "name": "Speaker"})
        self.assertEqual(controller.state, "Error")
        self.assertIn("Receiver rejected", controller.message)
        self.assertNotIn("private/live", controller.message)
        stream.close.assert_awaited_once()

    async def test_cast_module_uses_the_sidecar_interpreter_and_ignores_proxy_environment(self):
        child = AsyncMock()
        with patch("processes.importlib.util.find_spec", return_value=object()), \
             patch("processes.asyncio.create_subprocess_exec", new=AsyncMock(return_value=child)) as spawn:
            created = await self.processes.spawn(["catt", "--version"])
        self.assertIs(created, child)
        args = spawn.call_args.args
        self.assertEqual(args[-3:], ("-m", "catt.cli", "--version"))
        self.assertEqual(args[-4], sys.executable)
        self.assertEqual(spawn.call_args.kwargs["env"]["NO_PROXY"], "*")
        self.assertNotIn("HTTPS_PROXY", spawn.call_args.kwargs["env"])
        self.processes.children.discard(child)

    async def test_module_command_executes_without_a_global_cast_launcher(self):
        package = Path(self.temp.name) / "catt"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "cli.py").write_text("if __name__ == '__main__': print('catt v0.13.3')\n")
        self.processes.environment.update(PYTHONPATH=self.temp.name, PATH="/usr/bin")
        with patch("processes.importlib.util.find_spec", return_value=object()):
            result = await self.processes.run(["catt", "--version"])
        self.assertEqual(result.strip(), "catt v0.13.3")
        self.assertFalse(self.processes.children)

    async def test_settings_socket_updates_preferences_and_preserves_active_cast(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        server = SettingsServer(self.prefs, controller, controller.handle)
        await server.start()
        self.addAsyncCleanup(server.close)
        self.assertEqual(server.path.stat().st_mode & 0o777, 0o600)
        async def send(value):
            reader, writer = await asyncio.open_unix_connection(str(server.path))
            writer.write(json.dumps(value).encode() + b"\n")
            await writer.drain()
            response = json.loads(await reader.readline())
            writer.close(); await writer.wait_closed()
            return response
        reply = await send({"action": "settings", "values": {"format": "mp3", "manual_devices": [{"name": "Speaker", "host": "10.2.0.5"}]}})
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["snapshot"]["settings"]["format"], "mp3")
        self.assertEqual(reply["snapshot"]["devices"][0]["host"], "10.2.0.5")
        controller.state = "Casting"
        reply = await send({"action": "settings", "values": {"bitrate": 320}})
        self.assertFalse(reply["ok"])
        self.assertEqual(controller.state, "Casting")
        self.assertEqual(self.prefs.values["bitrate"], 192)
        self.assertFalse((await send({"action": "start", "id": "manual:10.2.0.5"}))["ok"])

    async def test_settings_app_can_save_while_plugin_is_not_running(self):
        reply = settings_request({"action": "settings", "values": {"stream_port": 48200}})
        self.assertTrue(reply["ok"])
        self.assertEqual(Preferences().values["stream_port"], 48200)
        with self.assertRaises(Failure):
            settings_request({"action": "start"})

    async def test_settings_server_refuses_an_existing_regular_file(self):
        path = self.prefs.runtime / "settings.sock"
        path.write_text("unrelated")
        server = SettingsServer(self.prefs, Controller(self.prefs, self.processes, lambda value: None), AsyncMock())
        with self.assertRaises(Failure):
            await server.start()
        self.assertEqual(path.read_text(), "unrelated")

    async def test_fixed_stream_port_reports_collision_before_capture(self):
        occupied = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
        port = occupied.sockets[0].getsockname()[1]
        stream = Stream(self.processes, "127.0.0.1", "127.0.0.1", port)
        try:
            with self.assertRaisesRegex(Failure, "in use"):
                await stream.start("dummy.monitor", 192)
            self.assertIsNone(stream.encoder)
        finally:
            occupied.close(); await occupied.wait_closed()

    async def test_timeout_reaps_only_owned_child(self):
        with self.assertRaises(Failure):
            await self.processes.run([sys.executable, "-c", "import time; time.sleep(30)"], .1)
        self.assertFalse(self.processes.children)

    async def test_cancellation_reaps_child(self):
        task = asyncio.create_task(self.processes.run([sys.executable, "-c", "import time; time.sleep(30)"], 60))
        await asyncio.sleep(.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertFalse(self.processes.children)

    async def test_monitor_selection_never_uses_microphone(self):
        runner = AsyncMock()
        runner.run.side_effect = [json.dumps([{"name": "speaker", "description": "Speakers", "monitor_source": "speaker.monitor"}]),
                                  json.dumps([{"index": 1, "name": "mic"}, {"index": 2, "name": "speaker.monitor"}]), "speaker\n"]
        found = await audio.sources(runner)
        self.assertEqual(audio.select(found, "default")["monitor"], "speaker.monitor")
        with self.assertRaises(Failure):
            audio.select(found, "mic")

    async def test_no_stop_is_sent_for_replacement_session(self):
        cast = Cast(self.processes)
        cast.info = AsyncMock(return_value={"content_id": "someone-elses-media"})
        cast.command = AsyncMock()
        await cast.stop_owned({"host": "192.168.1.5"}, "our-session")
        cast.command.assert_not_called()
        cast.info.return_value = {"content_id": "our-session"}
        await cast.stop_owned({"host": "192.168.1.5"}, "our-session")
        cast.command.assert_awaited_once_with({"host": "192.168.1.5"}, "stop")

    async def test_busy_receiver_never_receives_load(self):
        cast = Cast(self.processes)
        cast.info = AsyncMock(return_value={"app_id": "CC1AD845", "player_state": "PLAYING"})
        cast.command = AsyncMock()
        with self.assertRaisesRegex(Failure, "busy"):
            await cast.start({"host": "192.168.1.5"}, "our-session")
        cast.command.assert_not_called()

    async def test_stop_cancels_pending_connection_and_closes_stream(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.stream = AsyncMock()
        controller.stream.url = "our-session"
        stream = controller.stream
        controller.receiver = {"host": "192.168.1.5", "name": "Speaker"}
        controller.cast.stop_owned = AsyncMock()
        controller.operation = asyncio.create_task(asyncio.sleep(30))
        await controller.stop()
        stream.close.assert_awaited_once()
        self.assertEqual(controller.state, "Off")
        self.assertIsNone(controller.stream)

    async def test_http_has_no_directory_or_control_endpoint(self):
        stream = Stream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.server = await asyncio.start_server(stream.serve, "127.0.0.1", 0)
        self.addAsyncCleanup(stream.close)
        port = stream.server.sockets[0].getsockname()[1]
        for path, method, code in (("/", "GET", b"404"), ("/../settings.json", "GET", b"404"),
                                   (stream.path, "POST", b"405"), (stream.path, "HEAD", b"200")):
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(f"{method} {path} HTTP/1.1\r\nHost: test\r\n\r\n".encode())
            await writer.drain()
            self.assertIn(code, (await reader.read()).split(b"\r\n")[0])
            writer.close()
            await writer.wait_closed()
        stream.receiver = "192.168.1.5"
        stream.address = "192.168.1.2"
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(f"GET {stream.path} HTTP/1.1\r\nHost: test\r\n\r\n".encode())
        await writer.drain()
        self.assertIn(b"404", await reader.read())
        writer.close()
        await writer.wait_closed()

    async def test_stop_closes_a_live_http_reader_before_waiting_for_the_server(self):
        stream = Stream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.server = await asyncio.start_server(stream.serve, "127.0.0.1", 0)
        port = stream.server.sockets[0].getsockname()[1]
        stream.encoder = await self.processes.spawn([sys.executable, "-c",
            "import sys,time;sys.stdout.buffer.write(b'a'*4096);sys.stdout.flush();time.sleep(30)"])
        encoder = stream.encoder
        stream.pump = asyncio.create_task(stream.read_audio())
        await asyncio.wait_for(stream.ready.wait(), 1)
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(f"GET {stream.path} HTTP/1.1\r\nHost: test\r\n\r\n".encode())
        await writer.drain()
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1)
        try:
            # The reader deliberately stays connected: Stop must close it.
            await asyncio.wait_for(stream.close(), 1.5)
            self.assertIsNotNone(encoder.returncode)
            self.assertFalse(stream.clients)
            self.assertFalse(self.processes.children)
            await asyncio.wait_for(reader.read(), 1)
            # The listener is released for immediate reconnection.
            replacement = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", port)
            replacement.close(); await replacement.wait_closed()
        finally:
            writer.close(); await writer.wait_closed()
            await stream.close()

    async def test_stop_aborts_a_client_that_never_finishes_its_http_headers(self):
        stream = Stream(self.processes, "127.0.0.1", "127.0.0.1")
        stream.server = await asyncio.start_server(stream.serve, "127.0.0.1", 0)
        port = stream.server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /"); await writer.drain()
        async def accepted():
            while not stream.clients: await asyncio.sleep(0)
        try:
            await asyncio.wait_for(accepted(), 1)
            await asyncio.wait_for(stream.close(), .5)
            self.assertFalse(stream.clients)
            try:
                self.assertEqual(await asyncio.wait_for(reader.read(), .5), b"")
            except ConnectionResetError:
                pass  # An aborted partial request may end with TCP reset.
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionResetError:
                pass  # Stop aborts the unfinished request instead of flushing it.
            await stream.close()

    async def test_remote_stop_timeout_does_not_delay_local_capture_shutdown(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.stream = AsyncMock()
        controller.stream.url = "our-session"
        stream = controller.stream
        controller.receiver = {"host": "192.168.1.5", "name": "Speaker"}
        remote_entered = asyncio.Event()
        async def unreachable(*args):
            remote_entered.set()
            await asyncio.Event().wait()
        controller.cast.stop_owned = unreachable
        stopped = asyncio.create_task(controller.stop())
        await asyncio.wait_for(remote_entered.wait(), 1)
        await asyncio.sleep(.02)
        stream.close.assert_awaited_once()
        self.assertIsNone(controller.stream)
        await asyncio.wait_for(stopped, 6)
        self.assertEqual(controller.state, "Off")
        self.assertIn("did not confirm", controller.message)

    async def test_slow_receiver_buffering_is_not_abandoned_after_eight_polls(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        stream = AsyncMock()
        stream.url = "our-session"
        stream.receiver_reads = 4096
        idle = {"app_id": "CC1AD845", "player_state": "IDLE"}
        buffered = {"app_id": "CC1AD845", "player_state": "BUFFERING", "content_id": stream.url}
        playing = {**buffered, "player_state": "PLAYING"}
        controller.cast.info = AsyncMock(side_effect=[idle, *([buffered] * 10), playing])
        controller.cast.start = AsyncMock()
        controller.cast.stop_owned = AsyncMock()
        with patch("controller.HlsStream", return_value=stream), patch("controller.route", return_value="10.20.1.5"), \
             patch("controller.audio.sources", new=AsyncMock(return_value=[{"id": "speaker", "name": "Speaker", "default": True, "monitor": "speaker.monitor"}])), \
             patch("controller.asyncio.sleep", new=AsyncMock()):
            await controller.start({"id": "speaker", "host": "10.20.0.8", "name": "Speaker"})
        self.assertEqual(controller.state, "Casting")
        self.assertEqual(controller.cast.info.await_count, 12)
        await controller.close()

    async def test_concurrent_cancelled_close_still_reaps_encoder_once(self):
        stream = Stream(self.processes, "127.0.0.1", "127.0.0.1")
        encoder = stream.encoder = object()
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed_end(process):
            entered.set()
            await release.wait()
        with patch.object(self.processes, "end", new=AsyncMock(side_effect=delayed_end)) as end:
            first = asyncio.create_task(stream.close())
            await entered.wait()
            first.cancel()
            second = asyncio.create_task(stream.close())
            await asyncio.sleep(0)
            self.assertFalse(first.done())
            release.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
            self.assertIsInstance(results[0], asyncio.CancelledError)
            end.assert_awaited_once_with(encoder)
            self.assertIsNone(stream.encoder)


    async def test_encoder_failure_cleans_stream_and_returns_error(self):
        controller = Controller(self.prefs, self.processes, lambda value: None)
        controller.stream = AsyncMock()
        controller.stream.failure = "Stream failed: FFmpeg stopped"
        controller.stream.url = "our-session"
        controller.receiver = {"host": "192.168.1.5", "name": "Speaker"}
        controller.cast.stop_owned = AsyncMock(side_effect=Failure("Unreachable"))
        stream = controller.stream
        await asyncio.wait_for(controller.watch(), 3)
        stream.close.assert_awaited_once()
        self.assertIsNone(controller.stream)
        self.assertEqual(controller.state, "Error")


class ValidationTests(unittest.TestCase):
    def test_discovery_filters_addresses_and_marks_groups(self):
        receiver = {"uuid": "12345678-1234-1234-1234-123456789abc", "host": "192.168.1.5",
                    "friendly_name": "Living room", "port": 8009}
        self.assertTrue(devices(json.dumps({"x": receiver}))[0]["supported"])
        receiver["port"] = 42000
        self.assertFalse(devices(json.dumps({"x": receiver}))[0]["supported"])
        receiver["host"] = "8.8.8.8"
        self.assertEqual(devices(json.dumps({"x": receiver})), [])
        for address in ("127.0.0.1", "0.0.0.0", "224.0.0.251", "::1", "example.com", "192.168.1.5;reboot", None):
            with self.assertRaises(Failure):
                local_ip(address)


if __name__ == "__main__":
    unittest.main()
