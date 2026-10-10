"""Bounded inert source values, shared by directory/store/archive transports."""
import base64
import json
from pathlib import Path
import stat
from backend.paths import SafetyError, relative, digest, no_symlinks

MAX_FILES = 500
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
TEXT = {'.py', '.qml', '.js', '.json', '.svg', '.sh', '.md', '.txt', '.toml', '.ini', '.yaml', '.yml', '.desktop', '.csv'}
MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
        '.ico': 'image/vnd.microsoft.icon', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.flac': 'audio/flac',
        '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2', '.svg': 'image/svg+xml'}


def content(value):
    if not isinstance(value, (str, bytes)): raise SafetyError('Source values must be text or inert bytes')
    return value.encode('utf-8') if isinstance(value, str) else value


def decode_file(name, data):
    suffix = Path(name).suffix.lower()
    if suffix in MIME and suffix != '.svg': return data
    try:
        value = data.decode('utf-8')
        if '\0' in value: raise UnicodeError('NUL in text')
        return value
    except UnicodeError:
        if suffix in TEXT: raise SafetyError('Text source must be UTF-8 without NUL: ' + name)
        return data


def signature(suffix, data):
    if suffix == '.png': return data.startswith(b'\x89PNG\r\n\x1a\n')
    if suffix in {'.jpg', '.jpeg'}: return data.startswith(b'\xff\xd8\xff')
    if suffix == '.webp': return data.startswith(b'RIFF') and data[8:12] == b'WEBP'
    if suffix == '.gif': return data.startswith((b'GIF87a', b'GIF89a'))
    if suffix == '.ico': return data.startswith(b'\0\0\x01\0')
    if suffix == '.wav': return data.startswith(b'RIFF') and data[8:12] == b'WAVE'
    if suffix == '.mp3': return data.startswith(b'ID3') or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)
    if suffix == '.ogg': return data.startswith(b'OggS')
    if suffix == '.flac': return data.startswith(b'fLaC')
    if suffix == '.ttf': return data.startswith((b'\0\x01\0\0', b'true'))
    if suffix == '.otf': return data.startswith(b'OTTO')
    if suffix == '.woff': return data.startswith(b'wOFF')
    if suffix == '.woff2': return data.startswith(b'wOF2')
    return True


def checked(files, manifest=None, limit=MAX_SOURCE_BYTES):
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES: raise SafetyError('Source requires 1–500 files')
    total = 0
    declarations = (manifest or {}).get('resources', {})
    for name, value in files.items():
        relative(name)
        if name.split('/')[0] == '_venv': raise SafetyError('_venv is reserved for installed dependencies')
        if any(other.startswith(name + '/') for other in files): raise SafetyError('File/directory conflict: ' + name)
        data = content(value); total += len(data)
        if len(data) > MAX_FILE_BYTES or total > limit: raise SafetyError('Source exceeds file/total size limits')
        suffix = Path(name).suffix.lower()
        if suffix in TEXT and (not isinstance(value, str) or '\0' in value): raise SafetyError('Text source must be UTF-8 without NUL: ' + name)
        binary = isinstance(value, bytes) or suffix in MIME and suffix != '.svg'
        if binary and name not in declarations: raise SafetyError('Binary resource must be declared in schema 2 resources: ' + name)
        if name in declarations:
            item = declarations[name]
            if digest(data) != item['sha256']: raise SafetyError('Resource checksum mismatch: ' + name)
            if suffix in MIME and item['mime'] != MIME[suffix]: raise SafetyError('Resource MIME/extension mismatch: ' + name)
            if not signature(suffix, data): raise SafetyError('Resource signature/extension mismatch: ' + name)
    for name in declarations:
        if name not in files: raise SafetyError('Declared resource is missing: ' + name)
    return files


def read_directory(root):
    root = no_symlinks(root)
    files, total = {}, 0
    for path in sorted(root.rglob('*')):
        no_symlinks(path)
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)): raise SafetyError('Special source files are forbidden: ' + str(path))
        if any(x.startswith('.') or x in {'__pycache__', 'node_modules'} for x in path.relative_to(root).parts): continue
        if stat.S_ISDIR(mode): continue
        name = str(relative(path.relative_to(root).as_posix()))
        total += path.stat().st_size
        if path.stat().st_size > MAX_FILE_BYTES or total > MAX_SOURCE_BYTES or len(files) >= MAX_FILES: raise SafetyError('Source exceeds file/count/total limits')
        files[name] = decode_file(name, path.read_bytes())
    return files


def source_hash(files):
    # Preserve EVERY existing text-only fingerprint and store provenance.
    values = {name: {'binary_sha256': digest(value)} if isinstance(value, bytes) else value for name, value in files.items()}
    return digest(json.dumps(values, sort_keys=True, separators=(',', ':')).encode())


def serialize(files):
    return {name: {'base64': base64.b64encode(value).decode('ascii')} if isinstance(value, bytes) else value for name, value in files.items()}


def deserialize(files):
    result = {}
    for name, value in files.items():
        if isinstance(value, dict):
            if set(value) != {'base64'}: raise SafetyError('Invalid binary cache encoding')
            try: value = base64.b64decode(value['base64'], validate=True)
            except (ValueError, TypeError) as error: raise SafetyError('Invalid binary cache encoding') from error
        result[name] = value
    return result


def preview(files):
    return '\n\n'.join('FILE ' + name + '\n' + (value if isinstance(value, str) else f'Binary resource — {len(value)} bytes — SHA-256 {digest(value)}') for name, value in sorted(files.items()))
