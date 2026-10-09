#!/usr/bin/env python3
"""Event-driven line protocol. No idle polling; debounce with a bounded deadline."""
import json
import os
import selectors
import signal
import sys
import time
from domain import Model
from storage import Store, StorageError

DEBOUNCE_SECONDS = 0.65
MAX_SAVE_DELAY = 3.0
MAX_COMMAND_BYTES = 2 * 1024 * 1024


def emit(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'); sys.stdout.flush()


def main():
    store = None
    try:
        store = Store(); model = Model(store.read())
    except (OSError, ValueError) as error:
        emit({'type': 'fatal', 'error': str(error)})
        if store: store.close()
        return 2
    emit(model.snapshot())
    selector = selectors.DefaultSelector()
    selector.register(sys.stdin.fileno(), selectors.EVENT_READ)
    # Wake the selector on termination so shell shutdown flushes pending edits.
    read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    selector.register(read_fd, selectors.EVENT_READ)
    old_wakeup = signal.set_wakeup_fd(write_fd)
    old_handlers = {s: signal.signal(s, lambda *_: None) for s in (signal.SIGTERM, signal.SIGINT)}
    buffer = b''; dirty_since = None; deadline = None; quitting = False; writable = True
    def flush():
        nonlocal dirty_since, deadline, writable
        if dirty_since is None: return
        try:
            store.save(model.persisted())
            emit({'type': 'saved', 'revision': model.document['revision']})
            dirty_since = deadline = None
        except (OSError, ValueError) as error:
            writable = False; deadline = None
            emit({'type': 'fatal', 'error': 'Saving stopped: ' + str(error)})
    try:
        while not quitting:
            timeout = max(0, deadline - time.monotonic()) if deadline is not None else None
            events = selector.select(timeout)
            if not events: flush(); continue
            for key, _ in events:
                if key.fd == read_fd:
                    os.read(read_fd, 4096); quitting = True; break
                chunk = os.read(key.fd, 65536)
                if not chunk: quitting = True; break
                buffer += chunk
                if len(buffer) > MAX_COMMAND_BYTES and b'\n' not in buffer:
                    emit({'type': 'fatal', 'error': 'Oversized command'}); writable = False; quitting = True; break
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        if len(line) > MAX_COMMAND_BYTES: raise StorageError('Oversized command')
                        message = json.loads(line)
                        if not isinstance(message, dict): raise StorageError('Command must be an object')
                        if message.get('action') == 'quit': quitting = True; break
                        if message.get('action') == 'flush': flush(); continue
                        if not writable: raise StorageError('Storage is read-only after a save error; reload after resolving it.')
                        delta = model.command(message)
                        if delta:
                            emit(delta)
                            current = time.monotonic()
                            dirty_since = dirty_since if dirty_since is not None else current
                            deadline = min(current + DEBOUNCE_SECONDS, dirty_since + MAX_SAVE_DELAY)
                    except (ValueError, KeyError, TypeError) as error:
                        emit({'type': 'error', 'error': str(error)})
            # A continuously readable stdin must not starve the maximum deadline.
            if writable and deadline is not None and time.monotonic() >= deadline: flush()
        if writable: flush()
    finally:
        signal.set_wakeup_fd(old_wakeup)
        for s, handler in old_handlers.items(): signal.signal(s, handler)
        selector.close(); os.close(read_fd); os.close(write_fd); store.close()
    return 0 if writable else 2


if __name__ == '__main__': raise SystemExit(main())
