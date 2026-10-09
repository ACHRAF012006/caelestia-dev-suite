"""Declarative dashboard capability; no host destinations or executable patches."""
import re
from backend.paths import SafetyError, component_id, relative

TARGET = 'caelestia-dashboard'
RESERVED_IDS = {'dashboard', 'media', 'performance', 'weather', 'terminal', 'timer'}


def declaration(value):
    if not isinstance(value, dict) or set(value) != {'id', 'title', 'icon', 'component', 'order'}:
        raise SafetyError('dashboard requires exactly id, title, icon, component and order')
    component_id(value['id'])
    if value['id'] in RESERVED_IDS:
        raise SafetyError('Dashboard page ID is reserved by the host')
    if not isinstance(value['title'], str) or not 1 <= len(value['title']) <= 40 or any(ord(c) < 32 or ord(c) == 127 for c in value['title']):
        raise SafetyError('Dashboard title must be 1–40 printable characters')
    if not isinstance(value['icon'], str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', value['icon']):
        raise SafetyError('Dashboard icon must be a Material symbol name')
    relative(value['component'])
    if not value['component'].endswith('.qml') or not re.fullmatch(r'[A-Za-z0-9_/-]+\.qml', value['component']):
        raise SafetyError('Dashboard component must be a relative QML source path')
    if type(value['order']) is not int or not 1 <= value['order'] <= 1000:
        raise SafetyError('Dashboard order must be an integer from 1 to 1000')
    return dict(value)


def requested(manifest):
    return manifest.get('integration', {}).get('target') == TARGET
