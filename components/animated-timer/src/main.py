"""JSON-lines Quickshell sidecar with one authoritative engine and alarm."""
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import sys
import tempfile
import time
from engine import Engine
from alarm import Alarm, write_chime


def main():
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'animated-timer'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(state / 'engine.lock', 'a') as lock:
        limit = time.monotonic() + 3
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= limit:
                    print('Animated Timer engine already active', file=sys.stderr)
                    return 2
                time.sleep(0.05)
        def shutdown(signum, frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        engine = Engine(state / 'state.json')
        with selectors.DefaultSelector() as selector, tempfile.TemporaryDirectory(prefix='animated-timer-sound-') as temporary:
            sound = Path(temporary) / 'ring.wav'
            write_chime(sound)
            selector.register(sys.stdin, selectors.EVENT_READ, 'stdin')
            alarm = Alarm(engine, selector, sound)
            buffer = b''
            def publish():
                snapshot = engine.snapshot()
                if alarm.error:
                    snapshot['error'] = alarm.error
                print(json.dumps(snapshot), flush=True)
            try:
                alarm.sync(); publish()
                while True:
                    timeouts = [alarm.timeout()]
                    if engine.data['state'] == 'Running':
                        timeouts.append(min(1.0, max(0.01, engine.remaining())))
                    timeout = min((t for t in timeouts if t is not None), default=None)
                    events = selector.select(timeout)
                    engine.tick()
                    for key, _ in events:
                        if key.data != 'stdin':
                            alarm.read_notification(key)
                            continue
                        chunk = os.read(sys.stdin.fileno(), 8192)
                        if not chunk:
                            return 0
                        buffer += chunk
                        if len(buffer) > 65536:
                            return 3
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            try:
                                message = json.loads(line)
                                if message.get('action') == 'quit':
                                    return 0
                                engine.command(message)
                                alarm.sync(); publish()
                            except (ValueError, KeyError, TypeError, OverflowError):
                                print(json.dumps(dict(engine.snapshot(), error='Invalid timer command')), flush=True)
                    if not events or any(key.data != 'stdin' for key, _ in events):
                        alarm.sync(); publish()
            finally:
                alarm.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
