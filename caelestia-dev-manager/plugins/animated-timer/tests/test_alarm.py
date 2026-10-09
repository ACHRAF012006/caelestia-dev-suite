"""Alarm integration uses private XDG state and silent fake desktop commands."""
import importlib.util
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import wave
import pytest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('timer_alarm_test', SOURCE / 'src/alarm.py')
alarm_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alarm_module)


class Helper:
    def __init__(self, tmp):
        self.tmp = tmp
        self.log = tmp / 'events.jsonl'
        self.action = tmp / 'action'
        tools = tmp / 'bin'; tools.mkdir()
        script = '''import json, os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['TIMER_TEST_LOG'], 'a') as f:
    f.write(json.dumps([name, sys.argv[1:]]) + '\\n')
if name == 'notify-send':
    print(42, flush=True)
    while not pathlib.Path(os.environ['TIMER_TEST_ACTION']).exists(): time.sleep(0.02)
    print('stop', flush=True)
elif name == 'canberra-gtk-play': time.sleep(0.06)
elif name == 'gdbus' and 'org.freedesktop.DBus.GetNameOwner' in sys.argv:
    print("(':timer-test.1',)", flush=True)
'''
        for name in ('notify-send', 'canberra-gtk-play', 'gdbus'):
            path = tools / name
            path.write_text('#!' + str(Path(sys.executable).resolve()) + '\n' + script); path.chmod(0o700)
        self.env = dict(os.environ, XDG_STATE_HOME=str(tmp / 'state'),
                        PATH=str(tools) + os.pathsep + os.environ['PATH'],
                        TIMER_TEST_LOG=str(self.log), TIMER_TEST_ACTION=str(self.action))
        self.process = None
        self.selector = selectors.DefaultSelector()
        self.start()

    def start(self):
        self.process = subprocess.Popen([sys.executable, '-B', str(SOURCE / 'src/main.py')], env=self.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.set_blocking(self.process.stdout.fileno(), False)
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b''
        return self.wait(lambda s: True)

    def wait(self, condition, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                snapshot = json.loads(line)
                if condition(snapshot): return snapshot
            if self.selector.select(max(0, end - time.monotonic())):
                chunk = os.read(self.process.stdout.fileno(), 8192)
                assert chunk, 'Helper exited: ' + self.process.stderr.read().decode()
                self.buffer += chunk
        raise AssertionError('No expected timer snapshot')

    def command(self, **message):
        self.process.stdin.write(json.dumps(message).encode() + b'\n'); self.process.stdin.flush()
        return self.wait(lambda s: True)

    def complete(self):
        self.command(action='configure', seconds=1)
        self.command(action='start')
        return self.wait(lambda s: s['state'] == 'Completed' and s['alarm_active'])

    def events(self, name):
        if not self.log.exists(): return []
        return [row for line in self.log.read_text().splitlines() if (row := json.loads(line))[0] == name]

    def stop(self):
        if self.process is None: return
        self.selector.unregister(self.process.stdout)
        if self.process.poll() is None:
            self.process.stdin.write(b'{"action":"quit"}\n'); self.process.stdin.flush()
        self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr): stream.close()
        self.process = None

    def close(self):
        self.stop(); self.selector.close()


@pytest.fixture
def helper(tmp_path):
    helper = Helper(tmp_path)
    try: yield helper
    finally: helper.close()


def test_original_chime_is_valid_pcm(tmp_path):
    file = tmp_path / 'bell.wav'
    alarm_module.write_chime(file)
    with wave.open(str(file)) as sound:
        assert sound.getnchannels() == 1 and sound.getsampwidth() == 2
        assert sound.getnframes() / sound.getframerate() == 1.6
        assert any(sound.readframes(sound.getnframes()))


def test_rings_repeatedly_until_dashboard_stop(helper):
    snapshot = helper.complete()
    helper.wait(lambda s: s['alarm_active'], timeout=4)
    # The second event-driven alarm wake occurs at the next ring deadline.
    end = time.monotonic() + 4
    while len(helper.events('canberra-gtk-play')) < 2 and time.monotonic() < end:
        helper.wait(lambda s: s['alarm_active'])
    assert len(helper.events('canberra-gtk-play')) >= 2
    assert len(helper.events('notify-send')) == 1
    stopped = helper.command(action='dismiss-alarm')
    assert not stopped['alarm_active'] and stopped['state'] == 'Completed'
    helper.stop()  # Shutdown reaps the close-notification process.
    assert any('org.freedesktop.Notifications.CloseNotification' in event[1] for event in helper.events('gdbus'))
    assert json.loads((helper.tmp / 'state/animated-timer/state.json').read_text())['alarm_active'] is False
    helper.start()
    assert helper.command(action='snapshot')['alarm_active'] is False
    assert len(helper.events('notify-send')) == 1


def test_notification_stop_action_silences_alarm(helper):
    helper.complete()
    helper.wait(lambda s: s['alarm_notification'] == 42)
    helper.action.write_text('stop')
    stopped = helper.wait(lambda s: not s['alarm_active'])
    assert stopped['state'] == 'Completed'
    helper.stop()
    assert any('org.freedesktop.Notifications.CloseNotification' in event[1] for event in helper.events('gdbus'))
    args = helper.events('notify-send')[0][1]
    assert '--action=stop=Stop' in args and '--expire-time=0' in args


def test_pending_alarm_survives_restart_without_duplicate_notification(helper):
    helper.complete()
    before = helper.wait(lambda s: s['alarm_notification'] == 42)
    helper.stop()
    restored = helper.start()
    assert restored['alarm_active'] and restored['alarm_cycle'] == before['alarm_cycle']
    helper.wait(lambda s: s['alarm_notification'] == 42)
    assert '--replace-id=42' in helper.events('notify-send')[-1][1]
    assert helper.command(action='dismiss-alarm', cycle='stale')['alarm_active']
    assert not helper.command(action='dismiss-alarm', cycle=before['alarm_cycle'])['alarm_active']


def test_silent_preferences_do_not_spawn_desktop_commands(helper):
    helper.command(action='preferences', values={'sound': False, 'notification': False})
    helper.complete()
    assert not helper.events('canberra-gtk-play') and not helper.events('notify-send')
    assert not helper.command(action='dismiss-alarm')['alarm_active']

def test_restarted_notification_server_cannot_replace_foreign_id(helper):
    helper.complete()
    helper.wait(lambda s: s['alarm_notification'] == 42)
    helper.stop()
    command = helper.tmp / 'bin/gdbus'
    command.write_text(command.read_text().replace(':timer-test.1', ':timer-test.2'))
    helper.start()
    helper.wait(lambda s: s['alarm_notification'] == 42)
    assert '--replace-id=42' not in helper.events('notify-send')[-1][1]
    assert not helper.command(action='dismiss-alarm')['alarm_active']
