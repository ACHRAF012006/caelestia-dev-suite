"""Release/update policy changes source eligibility, never installed runtimes."""
from types import MappingProxyType
from packaging.version import Version, InvalidVersion
from backend.paths import SafetyError

CHANNELS = MappingProxyType({'Stable': 'main', 'Beta': 'beta', 'Development': 'development'})


def checked(policy):
    if not isinstance(policy, dict) or set(policy) != {'channel', 'version', 'ignored'}: raise SafetyError('Invalid update policy')
    if policy['channel'] not in CHANNELS or type(policy['ignored']) is not bool: raise SafetyError('Invalid update channel/ignore preference')
    if policy['version'] is not None:
        if not isinstance(policy['version'], str): raise SafetyError('Invalid pinned version')
        try: Version(policy['version'])
        except InvalidVersion as error: raise SafetyError('Invalid pinned version') from error
    return dict(policy)


def policy(record):
    return checked((record or {}).get('store_policy', {'channel': 'Stable', 'version': None, 'ignored': False}))


def eligibility(record, manifest, channel='Stable'):
    if channel not in CHANNELS: raise SafetyError('Unknown release channel')
    if record is None: return {'allowed': True, 'status': 'Normal updates'}
    preferences = policy(record)
    if preferences['ignored']: return {'allowed': False, 'status': 'Updates ignored'}
    if preferences['channel'] != channel: return {'allowed': False, 'status': 'Pinned to ' + preferences['channel'] + ' channel'}
    if preferences['version'] is not None and preferences['version'] != manifest['version']:
        return {'allowed': False, 'status': 'Pinned to version ' + preferences['version']}
    # A version pin also preserves the exact installed snapshot for same-version
    # remote rewrites. A pin is stronger than a semver label.
    if preferences['version'] is not None and (record or {}).get('installed'):
        return {'allowed': False, 'status': 'Pinned to version ' + preferences['version']}
    return {'allowed': True, 'status': 'Normal updates'}
