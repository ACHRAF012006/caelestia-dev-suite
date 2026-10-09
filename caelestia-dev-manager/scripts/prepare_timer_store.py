#!/usr/bin/env python3
"""Validate/export the complete Timer component as inert source. Never publish."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.codex.package import encode, parse
from backend.paths import SafetyError, atomic_write, no_symlinks
from backend.store import checked_files, source_hash
from backend.validators import validate
from backend.timer_integration import COMMIT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=(ROOT.parent if (ROOT.parent / 'components').is_dir() else ROOT) / 'components/animated-timer')
    parser.add_argument('--package', type=Path, default=ROOT / 'workspace/animated-timer.caelestia-dev-package')
    args = parser.parse_args()
    source = ROOT / 'plugins/animated-timer'
    files = {}
    for path in sorted(source.rglob('*')):
        if any(part in ('__pycache__', '.pytest_cache') for part in path.relative_to(source).parts):
            continue
        no_symlinks(path)
        if path.is_file():
            files[path.relative_to(source).as_posix()] = path.read_text()
    checked_files(files, 'animated-timer')
    manifest = json.loads(files['manifest.json'])
    validation = validate(files, manifest, {'plugin_supported': True, 'caelestia_commit': COMMIT})
    if not validation['valid']:
        raise SafetyError('\n'.join(validation['errors']))
    destination = no_symlinks(args.destination.absolute())
    if destination.exists():
        existing = {p.relative_to(destination).as_posix(): no_symlinks(p).read_text()
                    for p in destination.rglob('*') if p.is_file()}
        if existing != files:
            raise SafetyError('Destination differs from source; preserve/reconcile it or choose a new export path')
    else:
        destination.mkdir(parents=True)
        for name, text in files.items():
            atomic_write(destination / name, text.encode(), 0o644)
    # Keep file bytes identical through import: section markers need no extra
    # blank separator because every source file already ends with a newline.
    if any(not text.endswith('\n') for text in files.values()):
        raise SafetyError('Export source files must end with a newline')
    package = encode({}, manifest) + ''.join(f'--- FILE: {name} ---\n{text}' for name, text in files.items())
    imported = parse(package)
    checked_files(imported.files, 'animated-timer')
    if imported.files != files:
        raise SafetyError('Package round-trip changed source content')
    # Validate the exact paste/import mapping too.
    result = validate(imported.files, json.loads(imported.files['manifest.json']),
                      {'plugin_supported': True, 'caelestia_commit': COMMIT})
    if not result['valid']:
        raise SafetyError('\n'.join(result['errors']))
    atomic_write(no_symlinks(args.package.absolute()), package.encode(), 0o644)
    print(f'Validated {len(files)} files; source SHA-256 {source_hash(files)}')
    print(f'Store-ready tree: {destination}\nComplete paste/import package: {args.package}')

if __name__ == '__main__':
    main()
