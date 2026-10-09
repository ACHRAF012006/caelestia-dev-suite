"""Apply the reviewed preview/icon repair to its exact supported shell files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

BASE = Path(__file__).resolve().parent
MANIFEST = json.loads((BASE / 'manifest.json').read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def safe(path):
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlinked or unsafe shell/backup path: ' + str(path))
    return path


def read(path):
    safe(path)
    return path.read_bytes() if path.exists() else None


def write(path, data, mode):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.preview-icons-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def changes(shell):
    pending = []
    for rel, expected in MANIFEST['files'].items():
        path = shell / rel
        before = read(path)
        after = (BASE / 'files' / rel).read_bytes()
        if digest(after) != expected['after']:
            raise ValueError('Repair payload checksum differs: ' + rel)
        if digest(before) == expected['after']:
            continue
        if digest(before) != expected['before']:
            raise ValueError('Shell file has other changes; refusing to overwrite: ' + rel)
        pending.append((rel, before, after, path.stat().st_mode & 0o777 if before is not None else 0o644))
    return pending


def restore(shell, backup):
    receipt = json.loads(safe(backup / 'receipt.json').read_text())
    if receipt['shell'] != str(shell):
        raise ValueError('Backup belongs to a different shell directory')
    staged = []
    for row in receipt['files']:
        rel = row['path']
        if rel not in MANIFEST['files']:
            raise ValueError('Unexpected backup file')
        expected = MANIFEST['files'][rel]
        if row['before'] != expected['before'] or row['after'] != expected['after']:
            raise ValueError('Backup does not match this repair')
        current = read(shell / rel)
        if digest(current) == row['before']:
            continue
        if digest(current) != row['after']:
            raise ValueError('Shell changed after repair; refusing to overwrite: ' + rel)
        original = read(backup / rel)
        if digest(original) != row['before']:
            raise ValueError('Backup checksum differs: ' + rel)
        staged.append((rel, original, row['mode']))
    for rel, original, mode in staged:
        if original is None:
            (shell / rel).unlink()
        else:
            write(shell / rel, original, mode)
    print('Restored', len(staged), 'files. Restart caelestia-shell.service to load them.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell', type=Path, default=Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'quickshell/caelestia')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--apply', action='store_true')
    action.add_argument('--restore', type=Path, metavar='BACKUP')
    args = parser.parse_args()
    shell = safe(args.shell.absolute())
    if args.restore:
        restore(shell, args.restore.absolute())
        return
    pending = changes(shell)
    print('Verified:', len(pending), 'files need repair; other files are preserved.')
    if args.check or not pending:
        return
    data_home = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')).absolute()
    backup = safe(data_home / 'caelestia-shell-fixes' / ('preview-icons-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')))
    backup.mkdir(parents=True, mode=0o700)
    rows = []
    for rel, before, after, mode in pending:
        if before is not None:
            write(backup / rel, before, mode)
        rows.append({'path': rel, 'before': digest(before), 'after': digest(after), 'mode': mode})
    write(backup / 'receipt.json', (json.dumps({'shell': str(shell), 'files': rows}, indent=2) + '\n').encode(), 0o600)
    # Recheck after backup creation; later/unrelated edits must never be erased.
    if changes(shell) != pending:
        raise ValueError('Shell changed during review; retry')
    written = []
    try:
        for rel, before, after, mode in pending:
            write(shell / rel, after, mode)
            written.append((rel, before, mode))
    except BaseException:
        for rel, before, mode in reversed(written):
            if before is None:
                (shell / rel).unlink(missing_ok=True)
            else:
                write(shell / rel, before, mode)
        raise
    print('Backup:', backup)
    print('Applied. Restart caelestia-shell.service to load the repair.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from None
