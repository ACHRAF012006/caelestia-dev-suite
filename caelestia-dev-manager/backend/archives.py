"""Portable .cdmpkg ZIP transport. Metadata inspection precedes private staging."""
import io
import json
from pathlib import Path
import stat
import tempfile
import zipfile
from backend.paths import SafetyError, relative, digest, atomic_write, no_symlinks, inside
from backend.resources import (MAX_FILES, MAX_FILE_BYTES, MAX_SOURCE_BYTES, content, decode_file, checked, read_directory)
from backend.schemas import strict_json
from backend.validators import manifest_parse, validate

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def export(files, destination):
    manifest = manifest_parse(files['manifest.json'])
    checked(files, manifest)
    validation = validate(files, manifest)
    # Missing local host tools are transport diagnostics, not source corruption.
    errors = [e for e in validation['errors'] if not e.startswith('Missing system executable')]
    if errors: raise SafetyError('\n'.join(errors))
    metadata = {'format': 1, 'kind': 'component', 'component': manifest['id'], 'version': manifest['version'],
                'files': {name: {'sha256': digest(content(value)), 'size': len(content(value))} for name, value in sorted(files.items())}}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('package.json', json.dumps(metadata, sort_keys=True).encode())
        for name, value in sorted(files.items()):
            info = zipfile.ZipInfo('payload/' + name); info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content(value))
    path = no_symlinks(destination)
    if path.exists(): raise SafetyError('Export destination exists; choose a new filename')
    atomic_write(path, output.getvalue(), 0o600)
    return metadata


def read(path, staging_parent, context=None):
    path, staging_parent = no_symlinks(path), no_symlinks(staging_parent)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES: raise SafetyError('Archive exceeds 32 MiB or is not a regular file')
    def checkpoint():
        if context: context.checkpoint()
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not 2 <= len(members) <= MAX_FILES + 1: raise SafetyError('Archive file-count limit exceeded')
            names, total = set(), 0
            for info in members:
                checkpoint()
                relative(info.filename)
                if info.filename in names: raise SafetyError('Duplicate archive path')
                names.add(info.filename)
                mode = info.external_attr >> 16
                if (stat.S_IFMT(mode) not in {0, stat.S_IFREG} or mode & 0o7000 or info.is_dir() or info.extra):
                    raise SafetyError('Archive links, special entries, directories and nonstandard link metadata are forbidden')
                if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}: raise SafetyError('Unsupported encrypted/compressed archive')
                if info.file_size > MAX_FILE_BYTES: raise SafetyError('Archive member size limit exceeded')
                total += info.file_size
                if total > MAX_SOURCE_BYTES + 512 * 1024: raise SafetyError('Archive total size limit exceeded')
                if info.filename != 'package.json' and not info.filename.startswith('payload/'): raise SafetyError('Unexpected archive member')
            if 'package.json' not in names or archive.getinfo('package.json').file_size > 512 * 1024: raise SafetyError('Missing or oversized package metadata')
            meta = strict_json(archive.read('package.json'))
            if not isinstance(meta, dict) or set(meta) != {'format', 'kind', 'component', 'version', 'files'} or type(meta['format']) is not int or meta['format'] != 1 or meta['kind'] != 'component': raise SafetyError('Unsupported package metadata')
            if not isinstance(meta['files'], dict) or not 1 <= len(meta['files']) <= MAX_FILES: raise SafetyError('Invalid package file list')
            if names != {'package.json', *('payload/' + name for name in meta['files'])}: raise SafetyError('Archive checksum inventory does not match members')
            for name, item in meta['files'].items():
                relative(name)
                if not isinstance(item, dict) or set(item) != {'sha256', 'size'} or type(item['size']) is not int or item['size'] != archive.getinfo('payload/' + name).file_size: raise SafetyError('Invalid checksum/size metadata')
                if any(other.startswith(name + '/') for other in meta['files']): raise SafetyError('Archive file/directory conflict')
            staging_parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='archive-', dir=staging_parent) as directory:
                stage = Path(directory)
                for name, item in meta['files'].items():
                    checkpoint()
                    if context: context.report('Inspecting package file ' + name)
                    # zipfile checks CRC; read at most the admitted member limit.
                    with archive.open('payload/' + name) as stream: data = stream.read(MAX_FILE_BYTES + 1)
                    if len(data) != item['size'] or digest(data) != item['sha256']: raise SafetyError('Archive checksum mismatch: ' + name)
                    atomic_write(inside(stage, stage / name), data)
                files = read_directory(stage)
                manifest = manifest_parse(files.get('manifest.json', ''))
                checked(files, manifest)
                if (meta['component'], meta['version']) != (manifest['id'], manifest['version']): raise SafetyError('Archive manifest identity mismatch')
                validation = validate(files, manifest)
                errors = [e for e in validation['errors'] if not e.startswith('Missing system executable')]
                if errors: raise SafetyError('\n'.join(errors))
                return files, manifest, meta
    except (zipfile.BadZipFile, RuntimeError, KeyError, UnicodeError, TypeError) as error:
        raise SafetyError('Invalid component archive: ' + str(error)) from error
