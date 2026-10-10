import io
import json
import os
from pathlib import Path
import stat
import zipfile
import pytest
from backend.archives import export, read
from backend.paths import SafetyError, digest
from backend.resources import checked, source_hash, preview, read_directory


def binary_files(app_files):
    m, files = app_files
    data = b'\x89PNG\r\n\x1a\n\xff\x00inert image payload'
    m['schema_version'] = 2
    m['resources'] = {'assets/picture.png': {'sha256': digest(data), 'mime': 'image/png'}}
    files['manifest.json'] = json.dumps(m); files['assets/picture.png'] = data
    return m, files


def test_binary_package_roundtrip_install_restore_uninstall(manager, app_files, tmp_path):
    m, files = binary_files(app_files)
    package = tmp_path / 'transfer.cdmpkg'
    export(files, package)
    imported, manifest, metadata = read(package, tmp_path / 'staging')
    assert imported == files and manifest['id'] == m['id']
    assert not list((tmp_path / 'staging').iterdir())
    assert source_hash(imported) == source_hash(files)
    assert 'Binary resource' in preview(files) and digest(files['assets/picture.png']) in preview(files)
    manager.create(imported); manager.install(m['id'])
    backup = manager.backup(m['id'])
    path = manager.paths.root(m) / 'assets/picture.png'
    assert path.read_bytes() == files['assets/picture.png'] and not path.stat().st_mode & 0o111
    manager.uninstall(m['id']); manager.restore(backup['backup_id'])
    assert path.read_bytes() == files['assets/picture.png']
    assert manager.read_source(m['id']) == files


@pytest.mark.parametrize('attack', ['../escape', '/absolute', 'payload/../../escape', 'payload/../escape', 'payload/a\\b', 'C:/escape', 'payload/.git/config', 'payload/a//b'])
def test_archive_unsafe_metadata_paths_rejected(tmp_path, attack):
    path = tmp_path / 'attack.cdmpkg'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('package.json', '{}'); archive.writestr(attack, b'x')
    with pytest.raises(SafetyError): read(path, tmp_path / 'stage')
    assert not (tmp_path / 'stage').exists()


@pytest.mark.parametrize('mode', [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFDIR])
def test_archive_links_and_special_entries_refused(tmp_path, mode):
    path = tmp_path / 'special.cdmpkg'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('package.json', '{}')
        info = zipfile.ZipInfo('payload/evil'); info.external_attr = (mode | 0o644) << 16
        archive.writestr(info, b'../../external')
    with pytest.raises(SafetyError, match='special entries'): read(path, tmp_path / 'stage')


def test_archive_duplicate_checksum_and_size_limits(tmp_path, app_files, monkeypatch):
    m, files = binary_files(app_files); path = tmp_path / 'normal.cdmpkg'; export(files, path)
    with zipfile.ZipFile(path) as archive: values = {i.filename: archive.read(i) for i in archive.infolist()}
    bad = tmp_path / 'checksum.cdmpkg'
    values['payload/src/main.py'] = b'print("tampered")\n'
    with zipfile.ZipFile(bad, 'w') as archive:
        for name, value in values.items(): archive.writestr(name, value)
    with pytest.raises(SafetyError): read(bad, tmp_path / 'stage')
    monkeypatch.setattr('backend.archives.MAX_FILES', 2)
    with pytest.raises(SafetyError, match='file-count'): read(path, tmp_path / 'stage')
    monkeypatch.setattr('backend.archives.MAX_FILES', 500)
    monkeypatch.setattr('backend.archives.MAX_FILE_BYTES', 8)
    with pytest.raises(SafetyError, match='size limit'): read(path, tmp_path / 'stage')


def test_binary_requires_declaration_mime_and_signature(app_files):
    m, files = binary_files(app_files)
    checked(files, m)
    with pytest.raises(SafetyError, match='declared'): checked(files, {**m, 'resources': {}})
    m['resources']['assets/picture.png']['mime'] = 'image/jpeg'
    with pytest.raises(SafetyError, match='MIME'): checked(files, m)
    m['resources']['assets/picture.png']['mime'] = 'image/png'
    files['assets/picture.png'] = b'not a PNG'; m['resources']['assets/picture.png']['sha256'] = digest(files['assets/picture.png'])
    with pytest.raises(SafetyError, match='signature'): checked(files, m)


def test_directory_special_file_never_blocks_read(tmp_path, app_files):
    root = tmp_path / 'source'; root.mkdir(); os.mkfifo(root / 'blocking')
    with pytest.raises(SafetyError, match='Special source'): read_directory(root)


def test_text_fingerprints_keep_existing_provenance(app_files):
    files = app_files[1]
    assert source_hash(files) == digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


def test_store_binary_validation_and_cache(manager, app_files):
    from backend.store import checked_files, Store
    from backend.resources import serialize
    m, files = binary_files(app_files)
    assert checked_files(files)['resources'] == m['resources']
    store = Store(manager.paths); cache = store.cache_path(); cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({'repository': store.settings['repository'], 'branch': store.settings['branch'], 'commit': 'a' * 40,
                               'entries': [{'manifest': m, 'files': serialize(files)}]}))
    assert store.cached()['entries'][0]['files'] == files
