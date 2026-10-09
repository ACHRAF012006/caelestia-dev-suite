"""Single authoritative, suspend-aware timer. No dependency on Dev Manager."""
import json
import math
import os
from pathlib import Path
import time
import uuid

MAX_DURATION = 359999  # 99:59:59
PRESETS = [{'id': name.lower().replace(' ', '-'), 'name': name, 'seconds': seconds}
           for name, seconds in [('Focus', 1500), ('Short Break', 300), ('Study', 2700), ('Quick', 600)]]
DEFAULT_PREFS = {'sound': True, 'notification': True, 'repeat': False, 'animation': True}


class Clock:
    def now(self):
        # Unlike CLOCK_MONOTONIC, Linux BOOTTIME includes time spent suspended.
        return time.clock_gettime(time.CLOCK_BOOTTIME)

    def wall(self):
        return time.time()

    @property
    def boot(self):
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def duration(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Duration must be finite')
    return min(MAX_DURATION, max(0, int(value)))


class Engine:
    def __init__(self, path, clock=None, completed=None):
        self.path = Path(path)
        self.clock = clock or Clock()
        self.completed = completed or (lambda snapshot: None)
        self.data = {'state': 'Ready', 'configured': 1500, 'remaining': 1500,
                     'cycle_duration': 1500, 'cycle': '', 'notified': '', 'revision': 0,
                     'alarm_active': False, 'alarm_cycle': '', 'alarm_notification': 0, 'alarm_notification_owner': '',
                     'prefs': dict(DEFAULT_PREFS), 'presets': [dict(x) for x in PRESETS]}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text())
                if loaded['state'] not in ('Ready', 'Running', 'Paused', 'Completed'):
                    raise ValueError('Invalid state')
                for key in ('configured', 'remaining', 'cycle_duration'):
                    value = loaded[key]
                    duration(value)
                    if not 0 <= value <= MAX_DURATION or (key != 'remaining' and type(value) is not int):
                        raise ValueError('Invalid stored duration')
                if type(loaded.get('revision')) is not int or loaded['revision'] < 0 or any(not isinstance(loaded.get(k), str) for k in ('cycle', 'notified')):
                    raise ValueError('Invalid stored revision/cycle')
                if type(loaded.get('alarm_active', False)) is not bool or not isinstance(loaded.get('alarm_cycle', ''), str) or type(loaded.get('alarm_notification', 0)) is not int or loaded.get('alarm_notification', 0) < 0 or not isinstance(loaded.get('alarm_notification_owner', ''), str):
                    raise ValueError('Invalid alarm state')
                if loaded['state'] == 'Running':
                    if not isinstance(loaded.get('boot'), str) or any(type(loaded.get(k)) not in (int, float) or not math.isfinite(loaded[k]) for k in ('deadline', 'wall_deadline')):
                        raise ValueError('Invalid stored deadline')
                if not isinstance(loaded['prefs'], dict) or any(type(loaded['prefs'].get(k)) is not bool for k in DEFAULT_PREFS):
                    raise ValueError('Invalid preferences')
                if not isinstance(loaded['presets'], list) or len(loaded['presets']) > 64:
                    raise ValueError('Invalid presets')
                for preset in loaded['presets']:
                    if not isinstance(preset['id'], str) or not isinstance(preset['name'], str) or not 1 <= duration(preset['seconds']) <= MAX_DURATION:
                        raise ValueError('Invalid preset')
                self.data.update(loaded)
                if self.data['state'] == 'Running':
                    if self.data.get('boot') != self.clock.boot:
                        self._deadline(max(0, self.data['wall_deadline'] - self.clock.wall()))
                    else:
                        float(self.data['deadline'])
            except (ValueError, KeyError, TypeError, OverflowError):
                # Keep damaged state for diagnosis rather than silently overwrite it.
                self.path.rename(self.path.with_name('state-invalid-' + uuid.uuid4().hex + '.json'))
                self.__init__(self.path, self.clock, self.completed)
                return
        self.tick()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.tmp')
        with open(temporary, 'w', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(self.data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        fd = os.open(self.path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def remaining(self):
        return max(0, self.data['deadline'] - self.clock.now()) if self.data['state'] == 'Running' else self.data['remaining']

    def snapshot(self):
        remaining = self.remaining()
        return dict(self.data, remaining=math.ceil(remaining),
                    fraction=min(1, remaining / max(1, self.data['cycle_duration'])))

    def _deadline(self, seconds):
        self.data.update(deadline=self.clock.now() + seconds, wall_deadline=self.clock.wall() + seconds, boot=self.clock.boot)

    def start(self):
        if self.data['configured'] <= 0:
            return
        self.data.update(state='Running', cycle_duration=self.data['configured'],
                         remaining=self.data['configured'], cycle=uuid.uuid4().hex)
        self._deadline(self.data['configured'])

    def tick(self):
        if self.data['state'] != 'Running' or self.remaining() > 0:
            return False
        self.data.update(state='Completed', remaining=0)
        if not self.data['alarm_active']:
            self.data.update(alarm_active=True, alarm_cycle=self.data['cycle'], alarm_notification=0, alarm_notification_owner='')
        cycle = self.data['cycle']
        notify = self.data.get('notified') != cycle
        self.data['notified'] = cycle
        self.data['revision'] += 1
        # At-most-once: durable completion receipt BEFORE external effects.
        self.save()
        if notify:
            self.completed(self.snapshot())
        if self.data['prefs']['repeat']:
            # One completion after a long suspend; never replay missed cycles.
            self.start()
            self.data['revision'] += 1
            self.save()
        return True

    def command(self, message):
        self.tick()
        action = message.get('action')
        state = self.data['state']
        if action == 'start' and state in ('Ready', 'Completed'):
            self.start()
        elif action == 'pause' and state == 'Running':
            self.data.update(remaining=self.remaining(), state='Paused')
        elif action == 'resume' and state == 'Paused':
            self._deadline(self.data['remaining'])
            self.data['state'] = 'Running'
        elif action == 'dismiss-alarm':
            # A delayed notification from an earlier alarm must not silence a new one.
            if message.get('cycle', self.data['alarm_cycle']) != self.data['alarm_cycle']:
                return self.snapshot()
            self.data.update(alarm_active=False, alarm_cycle='', alarm_notification=0, alarm_notification_owner='')
        elif action == 'alarm-notification':
            identity = message['id']
            if not self.data['alarm_active'] or message.get('cycle') != self.data['alarm_cycle'] or type(identity) is not int or identity < 0:
                return self.snapshot()
            self.data['alarm_notification'] = identity
            self.data['alarm_notification_owner'] = str(message.get('owner', ''))
        elif action in ('reset', 'cancel'):
            self.data.update(alarm_active=False, alarm_cycle='', alarm_notification=0, alarm_notification_owner='')
            self.data.update(state='Ready', remaining=self.data['configured'], cycle_duration=self.data['configured'])
        elif action == 'configure':
            self.data['configured'] = duration(message['seconds'])
            if state in ('Ready', 'Completed'):
                self.data.update(state='Ready', remaining=self.data['configured'], cycle_duration=self.data['configured'])
        elif action == 'adjust':
            # Atomic unit edit avoids stale UI snapshots losing rapid wheel steps.
            unit = message['unit']
            if unit not in (0, 1, 2):
                raise ValueError('Invalid unit')
            factors = (3600, 60, 1)
            values = [self.data['configured'] // 3600, self.data['configured'] // 60 % 60, self.data['configured'] % 60]
            value = message.get('value')
            values[unit] = min(99 if unit == 0 else 59, max(0, int(value if value is not None else values[unit] + int(message['delta']))))
            return self.command({'action': 'configure', 'seconds': sum(v * f for v, f in zip(values, factors))})
        elif action == 'preferences':
            values = message['values']
            for key in DEFAULT_PREFS:
                if type(values.get(key)) is bool:
                    self.data['prefs'][key] = values[key]
        elif action == 'preset-save':
            name = str(message['name']).strip()[:40]
            seconds = duration(message['seconds'])
            if not name or seconds < 1:
                raise ValueError('Preset needs a name and positive duration')
            identity = message.get('id') or uuid.uuid4().hex
            presets = [p for p in self.data['presets'] if p['id'] != identity]
            if len(presets) >= 64:
                raise ValueError('Maximum 64 presets')
            self.data['presets'] = presets + [{'id': identity, 'name': name, 'seconds': seconds}]
        elif action == 'preset-delete':
            self.data['presets'] = [p for p in self.data['presets'] if p['id'] != message['id']]
        elif action != 'snapshot':
            return self.snapshot()
        self.data['revision'] += 1
        self.save()
        return self.snapshot()
