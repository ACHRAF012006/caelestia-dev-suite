"""Reviewed host matrix. Signatures authorize only these fixed adapters/files."""
from dataclasses import dataclass
from types import MappingProxyType
from backend.paths import SafetyError, digest, no_symlinks

COMMIT = 'e34b6957fad5ce9395841b65be9e3df180ccd65c'
CAST_FILES = {
    'modules/utilities/cards/Toggles.qml': 'fae4d5d5c4c56341b10aa66a79e016704d2c5d4a77b5f32b3b72cca4702967ba',
    'modules/nexus/pages/utilities/QuickTogglesPage.qml': '91785c48250415814ae9a85c2197d57b8a502406f62defdd950406f12fd33900',
}
DASHBOARD_FILES = {
    'modules/dashboard/Content.qml': 'd3daf3b27089c92681603b2bed1787ef8a428e48c63b219853fc6bb8b56e5e2f',
    'modules/dashboard/Wrapper.qml': '17d119e5c5e2727f68ee6800df933a618f3e3b21c153622fcbe318123231146d',
}


@dataclass(frozen=True)
class HostRule:
    adapter: str
    revision: int
    version: str
    commit: str
    files: dict
    allow_unmarked_signature: bool = False


HOST_RULES = MappingProxyType({
    'cast-audio': HostRule('cast-audio', 1, '2.5.1', COMMIT, MappingProxyType(CAST_FILES), True),
    'animated-timer': HostRule('animated-timer', 1, '2.5.1', COMMIT, MappingProxyType(DASHBOARD_FILES)),
    'dashboard-pages': HostRule('dashboard-pages', 1, '2.5.1', COMMIT, MappingProxyType(DASHBOARD_FILES)),
})


def release(paths, adapter):
    rule = HOST_RULES.get(adapter)
    if rule is None: return {'status': 'Adapter update required', 'detail': 'No reviewed adapter rule'}
    def marker(name):
        path = no_symlinks(paths.shell / name)
        if not path.exists(): return ''
        if not path.is_file() or path.stat().st_size > 4096: raise SafetyError('Invalid host release marker')
        return path.read_text().strip()
    try:
        commit = marker('.current_commit')
        version = marker('.current_version').removeprefix('VERSION=').lstrip('v')
    except (OSError, ValueError) as error:
        return {'status': 'Unsupported', 'detail': str(error)}
    if (version, commit) == (rule.version, rule.commit):
        return {'status': 'Verified', 'version': version, 'commit': commit, 'detail': 'Reviewed release markers; file signatures also required'}
    if not version and not commit and rule.allow_unmarked_signature:
        return {'status': 'Compatible by verified signature', 'detail': 'Unmarked Cast host requires exact reviewed file signatures'}
    return {'status': 'Unsupported', 'version': version, 'commit': commit,
            'detail': f'{adapter} requires verified Caelestia KDE v{rule.version} at {rule.commit}'}


def require_release(paths, adapter):
    result = release(paths, adapter)
    if result['status'] not in {'Verified', 'Compatible by verified signature'}: raise SafetyError(result['detail'])
    return result


def inspect(paths, adapter, expected=None):
    result = release(paths, adapter)
    if result['status'] not in {'Verified', 'Compatible by verified signature'}: return result
    rule = HOST_RULES[adapter]
    signatures = expected if expected is not None else rule.files
    try:
        if set(signatures) != set(rule.files): raise SafetyError('Unexpected adapter file signature set')
        for name, checksum in signatures.items():
            path = no_symlinks(paths.shell / name)
            if not path.is_file() or path.stat().st_size > 512 * 1024 or digest(path.read_bytes()) != checksum:
                raise SafetyError('Host modified or missing: ' + name)
    except (OSError, ValueError) as error:
        return {**result, 'status': 'Host modified', 'detail': str(error)}
    return {**result, 'adapter_revision': rule.revision, 'files': list(rule.files)}
