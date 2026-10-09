"""Dedicated fixed Timer dashboard bridge for the inspected Caelestia KDE release.

Component source cannot supply transformations, paths, or host code.
"""
import json
from backend.paths import SafetyError, atomic_write, digest, no_symlinks

TARGET = 'caelestia-dashboard-timer'
COMMIT = 'e34b6957fad5ce9395841b65be9e3df180ccd65c'
FILES = {
    'modules/dashboard/Content.qml': 'd3daf3b27089c92681603b2bed1787ef8a428e48c63b219853fc6bb8b56e5e2f',
    'modules/dashboard/Wrapper.qml': '17d119e5c5e2727f68ee6800df933a618f3e3b21c153622fcbe318123231146d',
}


def requested(manifest):
    return manifest.get('integration', {}).get('target') == TARGET


def panel_sources(originals):
    result = dict(originals)
    name = 'modules/dashboard/Content.qml'
    text = result[name].replace('    readonly property var dashboardTabs: {', '''    // BEGIN Dev Manager Timer adapter v1
    readonly property var timerPlugin: {
        const count = PluginLoader.loadedCount;
        return count > 0 ? PluginLoader.pluginInstances["animated-timer"] ?? null : null;
    }
    Component {
        id: timerComponent
        Loader {
            objectName: "animatedTimerPageLoader"
            sourceComponent: root.timerPlugin ? root.timerPlugin.timerPage : null
            onLoaded: item.presentationActive = Qt.binding(() => root.visibilities.dashboard && root.screenState.dashboardTab === root.dashboardTabs.length - 1)
        }
    }
    // END Dev Manager Timer adapter v1

    readonly property var dashboardTabs: {''', 1)
    text = text.replace('        return allTabs.filter(tab => tab.enabled);', '''        if (root.timerPlugin)
            allTabs.push({ component: timerComponent, iconName: "hourglass_top", text: qsTr("Timer"), enabled: true });
        return allTabs.filter(tab => tab.enabled);''', 1)
    result[name] = text
    name = 'modules/dashboard/Wrapper.qml'
    text = result[name].replace('import qs.utils\n', 'import qs.utils\nimport qs.services\n', 1)
    text = text.replace('    required property DrawerVisibilities visibilities', '''    // BEGIN Dev Manager Timer adapter v1
    readonly property var timerPlugin: {
        const count = PluginLoader.loadedCount;
        return count > 0 ? PluginLoader.pluginInstances["animated-timer"] ?? null : null;
    }
    // Retain the actual animated dashboard width when its content is unloaded.
    property real timerDashboardWidth: 854
    onWidthChanged: { if (content.active && width > 0) timerDashboardWidth = width; }
    function openTimerTab() {
        screenState.dashboardTab = [Config.dashboard.showDashboard, Config.dashboard.showMedia,
            Config.dashboard.showPerformance, Config.dashboard.showWeather,
            Config.dashboard.showTerminal].filter(value => value).length;
        visibilities.dashboard = true;
    }
    Loader {
        objectName: "animatedTimerNotchLoader"
        active: root.timerPlugin !== null
        sourceComponent: active ? root.timerPlugin.notchComponent : null
        onLoaded: item.host = root
    }
    // END Dev Manager Timer adapter v1

    required property DrawerVisibilities visibilities''', 1)
    result[name] = text
    return result


def receipt_path(paths):
    return no_symlinks(paths.manager / 'host-integrations/animated-timer.json')


def read_receipt(paths):
    path = receipt_path(paths)
    if not path.exists():
        return None, None
    if path.stat().st_size > 256 * 1024:
        raise SafetyError('Oversized Timer integration receipt')
    raw = path.read_text()
    try:
        receipt = json.loads(raw)
        if receipt['id'] != 'animated-timer' or receipt.get('adapter_version') != 1:
            raise ValueError()
        for key in ('originals', 'checksums', 'modes'):
            if set(receipt[key]) != set(FILES):
                raise ValueError()
        for name, value in receipt['originals'].items():
            if digest(value.encode()) != FILES[name] or type(receipt['modes'][name]) is not int or not 0 <= receipt['modes'][name] <= 0o777:
                raise ValueError()
        expected = panel_sources(receipt['originals'])
        if any(receipt['checksums'][name] != digest(value.encode()) for name, value in expected.items()):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise SafetyError('Invalid Timer integration receipt') from error
    return receipt, raw


def plan(paths, manifest):
    if manifest.get('id') != 'animated-timer':
        if requested(manifest):
            raise SafetyError('Timer adapter supports animated-timer only')
        return None
    receipt, raw = read_receipt(paths)
    wanted = requested(manifest)
    if not wanted and not receipt:
        return None
    # Installed release marker is checked in addition to exact host hashes.
    if no_symlinks(paths.shell / '.current_commit').read_text().strip() != COMMIT or no_symlinks(paths.shell / '.current_version').read_text().strip().removeprefix('VERSION=').lstrip('v') != '2.5.1':
        raise SafetyError('Timer integration requires verified Caelestia KDE v2.5.1 at ' + COMMIT)
    originals, before, modes = {}, {}, {}
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise SafetyError('Missing or oversized Timer host file: ' + str(path))
        current = path.read_text()
        mode = path.stat().st_mode & 0o777
        expected = receipt['checksums'][name] if receipt else FILES[name]
        if digest(current.encode()) != expected or (receipt and mode != receipt['modes'][name]):
            raise SafetyError('Timer host file changed; preserve/reconcile local edits before updating or removing: ' + str(path))
        originals[name] = receipt['originals'][name] if receipt else current
        before[name], modes[name] = current, mode
    after = panel_sources(originals) if wanted else originals
    updated = {'id': 'animated-timer', 'adapter_version': 1, 'originals': originals,
               'checksums': {name: digest(value.encode()) for name, value in after.items()}, 'modes': modes} if wanted else None
    return {'id': 'animated-timer', 'before': before, 'after': after, 'modes': modes,
            'receipt_before': raw, 'receipt_after': updated,
            'summary': ('Add the Timer dashboard tab and per-screen slim notch, enable the plugin and restart the Caelestia KDE shell.' if wanted else 'Remove the Timer bridge and restore the verified original dashboard files.')}


def check(paths, proposal):
    if proposal is None:
        return
    if proposal.get('id') != 'animated-timer' or any(set(proposal.get(key, {})) != set(FILES) for key in ('before', 'after', 'modes')):
        raise SafetyError('Invalid Timer host plan')
    # Re-derive the fixed output rather than accepting arbitrary proposal code.
    receipt, raw = read_receipt(paths)
    originals = receipt['originals'] if receipt else proposal['before']
    if any(digest(value.encode()) != FILES[name] for name, value in originals.items()):
        raise SafetyError('Invalid Timer host originals')
    wanted = proposal['receipt_after'] is not None
    if proposal['after'] != (panel_sources(originals) if wanted else originals):
        raise SafetyError('Invalid Timer host transformation')
    expected_receipt = {'id': 'animated-timer', 'adapter_version': 1, 'originals': originals,
                        'checksums': {n: digest(v.encode()) for n, v in proposal['after'].items()}, 'modes': proposal['modes']} if wanted else None
    if proposal['receipt_after'] != expected_receipt:
        raise SafetyError('Invalid Timer receipt plan')
    if raw != proposal['receipt_before']:
        raise SafetyError('Timer integration ownership changed since preview')
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if path.read_text() != proposal['before'][name] or path.stat().st_mode & 0o777 != proposal['modes'][name]:
            raise SafetyError('Timer host changed since preview')


def apply(paths, proposal):
    if proposal is None:
        return
    check(paths, proposal)
    for name in FILES:
        atomic_write(paths.shell / name, proposal['after'][name].encode(), proposal['modes'][name])
    path = receipt_path(paths)
    if proposal['receipt_after'] is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, json.dumps(proposal['receipt_after'], indent=2).encode(), 0o600)


def recover(paths, proposal):
    if proposal is None:
        return
    if proposal.get('id') != 'animated-timer' or any(set(proposal.get(key, {})) != set(FILES) for key in ('before', 'after', 'modes')):
        raise SafetyError('Invalid Timer recovery plan')
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if path.read_text() not in (proposal['before'][name], proposal['after'][name]) or path.stat().st_mode & 0o777 != proposal['modes'][name]:
            raise SafetyError('Timer host changed during recovery; preserve edits and reconcile manually')
    path = receipt_path(paths)
    after_raw = json.dumps(proposal['receipt_after'], indent=2) if proposal['receipt_after'] else None
    if (path.read_text() if path.exists() else None) not in (proposal['receipt_before'], after_raw):
        raise SafetyError('Timer receipt changed during recovery')
    for name in FILES:
        atomic_write(paths.shell / name, proposal['before'][name].encode(), proposal['modes'][name])
    if proposal['receipt_before'] is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, proposal['receipt_before'].encode(), 0o600)
