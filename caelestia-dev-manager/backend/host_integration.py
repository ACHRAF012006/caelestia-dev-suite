"""Manager-owned, checksum-pinned Cast menu adapter. No component patch is executed."""
import json
from pathlib import Path

from backend.paths import SafetyError, atomic_write, digest, no_symlinks

TARGET = "caelestia-quick-toggles"
FILES = {"modules/utilities/cards/Toggles.qml": "fae4d5d5c4c56341b10aa66a79e016704d2c5d4a77b5f32b3b72cca4702967ba",
         "modules/nexus/pages/utilities/QuickTogglesPage.qml": "91785c48250415814ae9a85c2197d57b8a502406f62defdd950406f12fd33900"}
LEGACY = {"modules/utilities/cards/Toggles.qml": "c0210e5be2d83ff8d239e131dc85bbe9d644101c328a24544a68ea344724b3b2",
          "modules/nexus/pages/utilities/QuickTogglesPage.qml": "dd3966990ca6b94d59bc2e79175cf57ce00beaa7f04db695c5fc3f7821f404a7"}


def requested(manifest):
    return manifest.get("integration", {}).get("target") == TARGET


def panel_sources(originals):
    result = dict(originals)
    name = "modules/utilities/cards/Toggles.qml"
    text = result[name]
    text = text.replace("    readonly property var quickToggles: {", '''    // BEGIN Dev Manager Cast menu adapter
    readonly property var castAudioPlugin: {
        const loaded = PluginLoader.loadedCount;
        const plugin = PluginLoader.pluginInstances["cast-audio"];
        return loaded > 0 && plugin && plugin.quickToggle ? plugin : null;
    }
    readonly property bool castAudioVisible: !(Config.utilities.quickToggles || [])
        .some(toggle => toggle.id === "castAudio" && toggle.enabled === false)
    Connections {
        target: root.castAudioPlugin
        ignoreUnknownSignals: true
        function onOpenMenuRequested() { root.visibilities.utilities = true; }
    }
    // END Dev Manager Cast menu adapter

    readonly property var quickToggles: {''', 1)
    text = text.replace("        return allToggles.filter(item => {", "        return allToggles.filter(item => {\n            if (item.id === \"castAudio\") return false;", 1)
    anchor = '''        QuickToggleRow {
            visible: root.needExtraRow
            model: root.needExtraRow ? root.quickToggles.slice(root.splitIndex) : []
        }'''
    text = text.replace(anchor, anchor + '''

        // BEGIN Dev Manager Cast menu row
        Loader {
            objectName: "castAudioMenuLoader"
            Layout.fillWidth: true
            active: root.castAudioVisible && root.castAudioPlugin !== null
            visible: active
            sourceComponent: active ? root.castAudioPlugin.quickToggle : null
        }
        // END Dev Manager Cast menu row''', 1)
    result[name] = text
    name = "modules/nexus/pages/utilities/QuickTogglesPage.qml"
    result[name] = result[name].replace('        { id: "wifi", label: qsTr("Wi-Fi") },', '        { id: "wifi", label: qsTr("Wi-Fi") },\n        { id: "castAudio", label: qsTr("Cast Audio") },', 1)
    return result


def pristine(name, value):
    if digest(value.encode()) == LEGACY[name]:
        if name.endswith("Toggles.qml"):
            value = value.replace("import QtQuick.Controls as Controls\n", "", 1)
            start = value.index("    // Cast Audio bridge")
            end = value.index("    readonly property var quickToggles:", start)
            value = value[:start] + value[end:]
            value = value.replace('            {\n                id: "castAudio"\n            },\n', "", 1)
            value = value.replace('            if (item.id === "castAudio") {\n                return root.castAudioPlugin !== null;\n            }\n\n', "", 1)
            start = value.index('                DelegateChoice {\n                    roleValue: "castAudio"')
            end = value.index('                DelegateChoice {\n                    roleValue: "wifi"', start)
            value = value[:start] + value[end:]
        else:
            value = value.replace('        { id: "castAudio", label: qsTr("Cast Audio") },\n', "", 1)
    if digest(value.encode()) != FILES[name]:
        raise SafetyError("Quick Toggles integration requires the verified Caelestia KDE host files. Preserve/reconcile local edits first: " + name)
    return value


def receipt_path(paths):
    return no_symlinks(paths.manager / "host-integrations/cast-audio.json")


def read_receipt(paths):
    path = receipt_path(paths)
    if not path.exists():
        return None, None
    if path.stat().st_size > 256 * 1024:
        raise SafetyError("Oversized host integration receipt")
    raw = path.read_text()
    try:
        receipt = json.loads(raw)
        if receipt["id"] != "cast-audio" or any(set(receipt[key]) != set(FILES) for key in ("originals", "checksums", "modes")):
            raise ValueError()
        for name, value in receipt["originals"].items():
            if digest(value.encode()) != FILES[name] or type(receipt["modes"][name]) is not int or not 0 <= receipt["modes"][name] <= 0o777:
                raise ValueError()
        expected = panel_sources(receipt["originals"])
        if receipt.get("adapter_version") != 1 or any(receipt["checksums"][name] != digest(value.encode()) for name, value in expected.items()):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise SafetyError("Invalid host integration receipt") from error
    return receipt, raw


def plan(paths, manifest):
    if manifest["id"] != "cast-audio":
        if requested(manifest):
            raise SafetyError("This verified Quick Toggles adapter currently supports Cast Audio only")
        return None
    receipt, raw = read_receipt(paths)
    wanted = requested(manifest)
    if not wanted and receipt is None:
        return None
    originals, before, modes = {}, {}, {}
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise SafetyError("Missing or oversized Quick Toggles host file: " + str(path))
        current = path.read_text()
        if receipt:
            if digest(current.encode()) != receipt["checksums"][name] or path.stat().st_mode & 0o777 != receipt["modes"][name]:
                raise SafetyError("Quick Toggles host file changed after integration; preserve/reconcile it before updating or removing: " + str(path))
            originals[name] = receipt["originals"][name]
        else:
            originals[name] = pristine(name, current)
        before[name] = current
        modes[name] = path.stat().st_mode & 0o777
    after = panel_sources(originals) if wanted else originals
    updated = {"id": "cast-audio", "adapter_version": 1, "originals": originals,
               "checksums": {name: digest(value.encode()) for name, value in after.items()}, "modes": modes} if wanted else None
    return {"id": "cast-audio", "before": before, "after": after, "modes": modes,
            "receipt_before": raw, "receipt_after": updated,
            "summary": ("Add the expandable Cast Audio row to Quick Toggles, enable the plugin and restart the Caelestia KDE shell." if wanted else "Remove the Cast menu bridge and restore the verified original host files.")}


def check(paths, proposal):
    if proposal is None:
        return
    if proposal.get("id") != "cast-audio" or any(set(proposal.get(key, {})) != set(FILES) for key in ("before", "after", "modes")):
        raise SafetyError("Invalid host integration plan")
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if path.read_text() != proposal["before"][name] or path.stat().st_mode & 0o777 != proposal["modes"][name]:
            raise SafetyError("Quick Toggles changed since the installation preview")
    path = receipt_path(paths)
    if (path.read_text() if path.exists() else None) != proposal["receipt_before"]:
        raise SafetyError("Host integration ownership changed since preview")


def apply(paths, proposal):
    if proposal is None:
        return
    check(paths, proposal)
    for name in FILES:
        atomic_write(paths.shell / name, proposal["after"][name].encode(), proposal["modes"][name])
    path = receipt_path(paths)
    if proposal["receipt_after"] is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, json.dumps(proposal["receipt_after"], indent=2).encode(), 0o600)


def recover(paths, proposal):
    if proposal is None:
        return
    # Never overwrite a third-party edit during crash recovery.
    for name in FILES:
        current = no_symlinks(paths.shell / name).read_text()
        if current not in (proposal["before"][name], proposal["after"][name]):
            raise SafetyError("Host file changed during interrupted integration; manual recovery required")
    for name in FILES:
        atomic_write(paths.shell / name, proposal["before"][name].encode(), proposal["modes"][name])
    path = receipt_path(paths)
    if proposal["receipt_before"] is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, proposal["receipt_before"].encode(), 0o600)

# Dispatch to independent, fixed adapters; never route dashboard changes through Cast.
from backend import timer_integration as _timer, dashboard_integration as _dashboard
_cast_requested, _cast_plan = requested, plan
_cast_check, _cast_apply, _cast_recover = check, apply, recover
_cast_receipt_path = receipt_path


def requested(manifest):
    return _cast_requested(manifest) or _timer.requested(manifest) or _dashboard.requested(manifest)


def plan(paths, manifest):
    if manifest.get('id') == 'cast-audio' or _cast_requested(manifest):
        return _cast_plan(paths, manifest)
    if _dashboard.participates(paths, manifest):
        return _dashboard.plan(paths, manifest)
    if manifest.get('id') == 'animated-timer' or _timer.requested(manifest):
        return _timer.plan(paths, manifest)
    return _cast_plan(paths, manifest)


def check(paths, proposal):
    if proposal and proposal.get('id') == _dashboard.ID:
        return _dashboard.check(paths, proposal)
    return (_timer.check if proposal and proposal.get('id') == 'animated-timer' else _cast_check)(paths, proposal)


def apply(paths, proposal):
    if proposal and proposal.get('id') == _dashboard.ID:
        return _dashboard.apply(paths, proposal)
    return (_timer.apply if proposal and proposal.get('id') == 'animated-timer' else _cast_apply)(paths, proposal)


def recover(paths, proposal):
    if proposal and proposal.get('id') == _dashboard.ID:
        return _dashboard.recover(paths, proposal)
    return (_timer.recover if proposal and proposal.get('id') == 'animated-timer' else _cast_recover)(paths, proposal)


def receipt_path(paths, component_id='cast-audio'):
    if component_id == 'cast-audio': return _cast_receipt_path(paths)
    shared, _ = _dashboard.read_receipt(paths)
    if shared and (component_id in shared['pages'] or component_id == 'animated-timer' and shared['timer']):
        return _dashboard.receipt_path(paths)
    return _timer.receipt_path(paths) if component_id == 'animated-timer' else _dashboard.receipt_path(paths)
