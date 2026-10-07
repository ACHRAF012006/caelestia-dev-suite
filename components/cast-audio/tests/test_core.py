"""Run: python3 -B -m unittest discover -s tests -v. No receiver is contacted."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import audio
from cast import Cast, devices, merge_devices
from settings_ipc import SettingsServer
from settings_client import request as settings_request
from controller import Controller
from processes import Processes
from safety import Failure, Preferences, local_ip
from stream import Stream


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
        with patch("controller.Stream", return_value=stream), patch("controller.route", return_value=stream.address), \
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
        with patch("controller.Stream", return_value=stream), patch("controller.route", return_value="10.20.1.5"), \
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
        reply = await send({"action": "settings", "values": {"manual_devices": [{"name": "Speaker", "host": "10.2.0.5"}]}})
        self.assertTrue(reply["ok"])
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
