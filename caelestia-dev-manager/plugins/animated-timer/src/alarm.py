"""One bounded alarm player and one actionable notification per pending alarm."""
import ast
import math
import os
from pathlib import Path
import struct
import subprocess
import time
import wave


def write_chime(path):
    """Original soft bell, independent of whether the desktop theme has a sound."""
    rate = 24000
    samples = bytearray()
    for i in range(int(rate * 1.6)):
        t = i / rate
        sample = 0.0
        for start, frequency in ((0, 523.25), (0.38, 659.25), (0.76, 783.99)):
            elapsed = t - start
            if elapsed >= 0:
                envelope = min(1, elapsed / 0.008) * math.exp(-elapsed * 6)
                sample += envelope * (math.sin(2 * math.pi * frequency * elapsed) + 0.18 * math.sin(2 * math.pi * frequency * 2.01 * elapsed))
        samples.extend(struct.pack('<h', int(max(-1, min(1, sample * 0.24)) * 32767)))
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(samples)


class Alarm:
    def __init__(self, engine, selector, sound_path, popen=subprocess.Popen, now=time.monotonic):
        self.engine, self.selector, self.sound_path = engine, selector, Path(sound_path)
        self.popen, self.now = popen, now
        self.sound = self.notification = self.closer = None
        self.cycle = ''
        self.notification_id = engine.data['alarm_notification']
        self.notification_owner = engine.data['alarm_notification_owner']
        self.notification_attempted = False
        self.next_ring = 0
        self.sound_started = 0
        self.buffer = b''
        self.error = ''

    def spawn(self, command, **kwargs):
        try:
            return self.popen(command, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              stdout=kwargs.pop('stdout', subprocess.DEVNULL), **kwargs)
        except OSError:
            return None

    @staticmethod
    def terminate(process):
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=0.3)
        else:
            process.wait()

    @staticmethod
    def server_owner():
        # Notification IDs belong to a server connection, and can be reused after
        # Caelestia's notification server restarts. Never replace/close a foreign ID.
        try:
            result = subprocess.run(['gdbus', 'call', '--timeout=1', '--session', '--dest',
                'org.freedesktop.DBus', '--object-path', '/org/freedesktop/DBus', '--method',
                'org.freedesktop.DBus.GetNameOwner', 'org.freedesktop.Notifications'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=1.2, text=True)
            owner = ast.literal_eval(result.stdout.strip())[0] if result.returncode == 0 else ''
            return owner if isinstance(owner, str) and owner.startswith(':') else ''
        except (OSError, subprocess.TimeoutExpired, ValueError, SyntaxError, IndexError, TypeError):
            return ''

    def stop_notification(self, close=True):
        if self.notification is not None:
            self.selector.unregister(self.notification.stdout)
            self.terminate(self.notification)
            self.notification.stdout.close()
            self.notification = None
        if close and self.notification_id and self.notification_owner and self.notification_owner == self.server_owner():
            self.terminate(self.closer)
            self.closer = self.spawn(['gdbus', 'call', '--timeout=1', '--session', '--dest', 'org.freedesktop.Notifications',
                '--object-path', '/org/freedesktop/Notifications', '--method',
                'org.freedesktop.Notifications.CloseNotification', str(self.notification_id)])
        if close:
            self.notification_id = 0; self.notification_owner = ''
        self.buffer = b''

    def sync(self):
        data = self.engine.data
        if self.closer is not None and self.closer.poll() is not None:
            self.closer.wait(); self.closer = None
        if not data['alarm_active']:
            self.terminate(self.sound); self.sound = None
            self.stop_notification()
            self.cycle = ''; self.notification_attempted = False; self.error = ''
            return
        if self.cycle != data['alarm_cycle']:
            self.stop_notification(close=False)
            self.cycle = data['alarm_cycle']
            self.notification_id = data['alarm_notification']
            self.notification_owner = data['alarm_notification_owner']
            self.notification_attempted = False
            self.next_ring = 0
        prefs = data['prefs']
        if not prefs['notification']:
            self.stop_notification(); self.notification_attempted = False
        elif not self.notification_attempted:
            self.notification_attempted = True
            command = ['notify-send', '--app-name=Caelestia Timer', '--icon=hourglass',
                       '--urgency=critical', '--expire-time=0', '--hint=boolean:resident:true',
                       '--hint=boolean:suppress-sound:true', '--print-id', '--action=stop=Stop', '--wait']
            owner = self.server_owner()
            if self.notification_id and (not owner or owner != self.notification_owner):
                self.notification_id = 0
            self.notification_owner = owner
            if self.notification_id:
                command += ['--replace-id=' + str(self.notification_id)]
            command += ['Timer completed', '']
            self.notification = self.spawn(command, stdout=subprocess.PIPE)
            if self.notification is not None:
                os.set_blocking(self.notification.stdout.fileno(), False)
                self.selector.register(self.notification.stdout, 1, ('alarm', self.cycle, self.notification))
            else:
                self.error = 'Timer notification unavailable.'
        if not prefs['sound']:
            self.terminate(self.sound); self.sound = None
        else:
            if self.sound is not None and self.sound.poll() is None and self.now() - self.sound_started > 4:
                self.terminate(self.sound); self.sound = None
                self.error = 'Alarm sound player did not respond.'
            if self.sound is not None and self.sound.poll() is not None:
                if self.sound.returncode:
                    self.error = 'Alarm sound could not be played.'
                self.sound.wait(); self.sound = None
            if self.sound is None and self.now() >= self.next_ring:
                self.sound = self.spawn(['canberra-gtk-play', '--file=' + str(self.sound_path),
                                         '--description=Caelestia Timer alarm', '--cache-control=never'])
                self.sound_started = self.now()
                self.next_ring = self.sound_started + 2
                if self.sound is None:
                    self.error = 'Alarm sound player unavailable.'

    def read_notification(self, key):
        _, cycle, process = key.data
        if process is not self.notification:
            return
        chunk = os.read(key.fileobj.fileno(), 4096)
        if not chunk:
            self.stop_notification(close=False)
            return
        self.buffer += chunk
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            line = line.strip()
            if line.isdigit():
                self.notification_id = int(line)
                self.notification_owner = self.server_owner()
                self.engine.command({'action': 'alarm-notification', 'cycle': cycle, 'id': self.notification_id, 'owner': self.notification_owner})
            elif line == b'stop':
                self.engine.command({'action': 'dismiss-alarm', 'cycle': cycle})

    def timeout(self):
        # Notification actions are event driven; wake only for the next bell/reap.
        if self.closer is not None:
            return 0.2
        if self.engine.data['alarm_active'] and self.engine.data['prefs']['sound']:
            if self.sound is not None and self.now() >= self.next_ring:
                return 0.5
            return max(0.05, min(2, self.next_ring - self.now()))
        return None

    def close(self):
        self.terminate(self.sound); self.sound = None
        self.stop_notification()
        if self.closer is not None:
            try:
                self.closer.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.terminate(self.closer)
            self.closer = None
