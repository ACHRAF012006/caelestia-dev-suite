"""Static validation: never import or execute component source."""
import ast
import json
import re
import shutil
from backend.paths import SafetyError, component_id, relative

TYPES = {"standalone-app", "caelestia-plugin", "user-service", "script", "kde-integration", "qml-component"}
RUNTIMES = {"python", "python-pyside6", "shell", "qml", "quickshell", "none"}

def manifest_parse(text):
    from backend.schemas import parse
    return parse(text)


def _validate_manifest(m, schema):
    allowed = {"id", "name", "version", "description", "type", "runtime", "entrypoint", "args", "dependencies",
               "desktop", "service", "compatibility", "permissions", "integration", "schema_version"}
    from backend.schemas import SCHEMAS
    allowed |= SCHEMAS[schema]
    if set(m) - allowed: raise SafetyError(f"Unknown manifest fields: {sorted(set(m)-allowed)}")
    try: component_id(m.get("id"))
    except SafetyError as error: raise SafetyError("id: " + str(error)) from error
    for key in ("name", "version", "description"):
        if not isinstance(m.get(key, ""), str) or any(ord(c) < 32 for c in m.get(key, "")):
            raise SafetyError(f"Invalid {key}")
    if not m.get("name") or len(m["name"]) > 120: raise SafetyError("Name is required (max 120)")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", m.get("version", "")):
        raise SafetyError("Version must have major.minor.patch format")
    if m.get("type") not in TYPES: raise SafetyError("Unsupported component type")
    if m.get("runtime") not in RUNTIMES: raise SafetyError("Unsupported runtime")
    if m.get("entrypoint"): relative(m["entrypoint"])
    if not isinstance(m.get("args", []), list) or any(not isinstance(x, str) or any(ord(c) < 32 or ord(c) == 127 for c in x) for x in m.get("args", [])):
        raise SafetyError("args must be a list of safe strings")
    specs = {"dependencies": {"system", "python"}, "desktop": {"icon", "terminal", "categories", "createShortcut", "startupNotify"},
             "service": {"restart"}, "compatibility": {"plasma", "caelestia_commit", "manager_min_version", "python"},
             "integration": {"target", "dashboard"}}
    for key, fields in specs.items():
        value = m.get(key, {})
        if not isinstance(value, dict) or set(value) - fields: raise SafetyError(f"Invalid {key} fields")
    deps = m.get("dependencies", {})
    for key in ("system", "python"):
        if not isinstance(deps.get(key, []), list) or any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:[<>=!~]{1,2}[A-Za-z0-9.*+-]+)?", s) for s in deps.get(key, [])):
            raise SafetyError(f"Invalid {key} dependencies; URLs/options/scripts are not allowed")
    for dep in deps.get("system", []):
        if not re.fullmatch(r"[A-Za-z0-9_.+-]+", dep): raise SafetyError("System dependencies are executable names")
    if m.get("desktop", {}).get("icon"): relative(m["desktop"]["icon"])
    if "terminal" in m.get("desktop", {}) and not isinstance(m["desktop"]["terminal"], bool): raise SafetyError("terminal must be boolean")
    for option in ("createShortcut", "startupNotify"):
        if option in m.get("desktop", {}) and not isinstance(m["desktop"][option], bool): raise SafetyError(f"desktop.{option} must be boolean")
    if m.get("desktop", {}).get("createShortcut", False) and m["type"] not in {"standalone-app", "script"}:
        raise SafetyError("Desktop shortcuts require a directly launchable standalone app or script")
    if "categories" in m.get("desktop", {}) and not re.fullmatch(r"(?:[A-Za-z]+;)+", m["desktop"]["categories"]): raise SafetyError("Invalid desktop categories")
    if m.get("service", {}).get("restart", "no") not in {"no", "on-failure", "always"}: raise SafetyError("Invalid service restart policy")
    if not isinstance(m.get("permissions", []), list) or any(not isinstance(x, str) for x in m.get("permissions", [])): raise SafetyError("permissions must be descriptive strings")
    if any(not isinstance(v, str) for v in m.get("compatibility", {}).values()): raise SafetyError("Compatibility values must be strings")
    from backend.capabilities import capabilities
    capabilities.validate_manifest(m)
    minimum = m.get('compatibility', {}).get('manager_min_version')
    if minimum is not None and not re.fullmatch(r'\d+\.\d+\.\d+', minimum):
        raise SafetyError('manager_min_version must be major.minor.patch')
    python = m.get('compatibility', {}).get('python')
    if python is not None:
        from packaging.specifiers import SpecifierSet, InvalidSpecifier
        try: SpecifierSet(python)
        except InvalidSpecifier as error: raise SafetyError('compatibility.python: invalid Python version specifier') from error
    if 'resources' in m:
        resources = m['resources']
        if not isinstance(resources, dict) or len(resources) > 500: raise SafetyError('resources: expected at most 500 resource descriptors')
        for path, item in resources.items():
            relative(path)
            if not isinstance(item, dict) or set(item) != {'sha256', 'mime'}: raise SafetyError('resources.' + path + ': requires sha256 and mime')
            if not isinstance(item['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']): raise SafetyError('resources.' + path + '.sha256: invalid checksum')
            if not isinstance(item['mime'], str) or not re.fullmatch('[a-z0-9.+-]+/[a-z0-9.+-]+', item['mime']): raise SafetyError('resources.' + path + '.mime: invalid MIME type')
    if 'portable_data' in m:
        items = m['portable_data']
        if not isinstance(items, list) or len(items) > 32: raise SafetyError('portable_data: expected at most 32 locations')
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {'root', 'path'} or item['root'] not in {'data', 'config', 'state'}: raise SafetyError('portable_data: requires root (data/config/state) and path')
            path = relative(item['path'])
            if not str(path).startswith('caelestia-components/' + m['id'] + '/'):
                raise SafetyError('portable_data.path: must be a child of caelestia-components/' + m['id'])
            if (item['root'], str(path)) in seen: raise SafetyError('portable_data: duplicate location')
            seen.add((item['root'], str(path)))
    return m

def validate(files, manifest, environment=None):
    errors, warnings = [], []
    try:
        manifest = manifest_parse(json.dumps(manifest))
        for path in files: relative(path)
    except SafetyError as e:
        return {"errors": [str(e)], "warnings": [], "valid": False}
    if manifest.get('integration', {}).get('target') == 'caelestia-dashboard':
        if manifest['integration']['dashboard']['component'] not in files:
            errors.append('Dashboard component must exist in source')
        warnings.append('Requires Dev Manager 0.7.0+ and verified Caelestia KDE v2.5.1. Installation reviews a shared dashboard bridge and restarts the shell.')
    minimum = manifest.get('compatibility', {}).get('manager_min_version')
    if minimum:
        from packaging.version import Version
        from backend.paths import VERSION
        if Version(VERSION) < Version(minimum): errors.append('Requires Dev Manager ' + minimum + ' or newer')
    entry = manifest.get("entrypoint")
    if not entry or entry not in files: errors.append("Entrypoint must exist in source")
    expected = {"python": ".py", "python-pyside6": ".py", "shell": ".sh", "qml": ".qml", "quickshell": ".qml"}
    if entry and manifest["runtime"] in expected and not entry.endswith(expected[manifest["runtime"]]): errors.append("Entrypoint extension does not match runtime")
    for path, data in files.items():
        if path.endswith(".py"):
            try: ast.parse(data, filename=path)
            except (SyntaxError, ValueError) as e: errors.append(f"{path}: {e}")
        if path.endswith(("install.sh", "setup.py")): warnings.append(f"{path} is inert source; manager will never run it as an install hook")
    if manifest["type"] == "kde-integration": errors.append("KDE integration adapter is reserved; target-specific support is not yet implemented")
    if manifest["type"] in {"caelestia-plugin", "qml-component"}:
        if "metadata.json.disabled" in files: errors.append("metadata.json.disabled is reserved for manager activation state")
        if manifest["runtime"] != "quickshell": errors.append("Caelestia components require quickshell runtime")
        if manifest["type"] == "qml-component" and manifest.get("integration", {}).get("target") != "caelestia-plugin":
            errors.append("QML components currently require integration.target = caelestia-plugin")
        try:
            meta = json.loads(files.get("metadata.json", "{}"))
            if meta.get("id") != manifest["id"] or meta.get("type") != "quickshell": errors.append("metadata.json requires matching id and type quickshell")
            if meta.get("ui", "main.qml") != entry: errors.append("metadata.json ui must match manifest entrypoint")
            for key in ("id", "name", "version", "description"):
                if meta.get(key) != manifest.get(key, ""): errors.append(f"metadata.json {key} must match manifest")
        except (ValueError, AttributeError): errors.append("Invalid Caelestia metadata.json")
        if environment and not environment.get("plugin_supported"): errors.append("Installed Caelestia plugin architecture could not be verified")
        if manifest.get("integration", {}).get("target") == "caelestia-dashboard-timer":
            warnings.append("Installation enables Animated Timer, adds its reviewed dashboard bridge and restarts the Caelestia KDE shell. Requires the Timer-capable manager release.")
        warnings.append("Installation enables Cast Audio, integrates its menu into Quick Toggles and restarts the Caelestia KDE shell after review." if manifest.get("integration", {}).get("target") == "caelestia-quick-toggles" else "Plugin installation/activation requires an explicit Caelestia shell restart. No dashboard registration API is assumed.")
    elif manifest["runtime"] not in {"python", "python-pyside6", "shell", "qml"}:
        errors.append("This component type needs a Python, shell, or standalone QML runtime")
    for name in manifest.get("dependencies", {}).get("system", []):
        if not shutil.which(name): errors.append(f"Missing system executable: {name} (install manually)")
    if manifest["runtime"] == "qml" and not shutil.which("qml6"): errors.append("Missing system executable qml6")
    if manifest["runtime"] == "python-pyside6" and not any(x.lower().startswith("pyside6") for x in manifest.get("dependencies", {}).get("python", [])):
        errors.append("python-pyside6 requires a declared PySide6 Python dependency")
    if manifest.get("desktop", {}).get("icon") not in (None, "") and manifest["desktop"]["icon"] not in files: errors.append("Desktop icon is missing")
    if environment:
        compat = manifest.get("compatibility", {})
        if compat.get("plasma") and not environment.get("plasma_version", "").startswith(compat["plasma"]): errors.append("Incompatible Plasma version prefix")
        if compat.get("caelestia_commit") and compat["caelestia_commit"] != environment.get("caelestia_commit"): errors.append("Incompatible Caelestia commit")
    warnings.append("Static checks cannot establish that pasted code is safe. Review source before launching or enabling.")
    return {"errors": errors, "warnings": warnings, "valid": not errors}
