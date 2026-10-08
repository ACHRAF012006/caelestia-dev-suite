import json
from pathlib import Path
from backend.paths import VERSION
from backend.desktop import desktop_directory
from backend.paths import SafetyError
from backend.store import DEFAULT_REPOSITORY

READ_FIRST = ["PROJECT_CONTEXT.md", "README.md", "docs/ARCHITECTURE.md", "docs/PLUGIN_SPEC.md",
              "docs/COMPONENT_SPEC.md", "docs/CODEX_PACKAGE_FORMAT.md", "docs/CODEX_WORKFLOW.md",
              "docs/COMPONENT_STORE.md", "docs/QUICK_TOGGLES_INTEGRATION.md"]

def context(manager, request, statuses=None, dependencies=None):
    components = [{"id": r["id"], "type": r["manifest"]["type"], "version": r["manifest"]["version"],
                   "runtime": r["manifest"]["runtime"], "entrypoint": r["manifest"].get("entrypoint"),
                   "dependencies": r["manifest"].get("dependencies", {}),
                   "validation": r.get("validation", {}),
                   "dependency_report": (dependencies or {}).get(r["id"]),
                   "source_hash": r.get("source_hash"), "store_origin": r.get("store_origin"),
                   "installed_version": r.get("installed_manifest", {}).get("version"),
                   "installed": r.get("installed", False), "enabled": r.get("enabled", False),
                   "status": r["status"], "source": str(manager.paths.source(r["id"])),
                   "desktop_shortcut_created": r["desktop_shortcut_created"],
                   "desktop_shortcut_path": (r.get("desktop_shortcut") or {}).get("path")} for r in (manager.all_status() if statuses is None else statuses)]
    try:
        directory = desktop_directory(manager.paths)
        desktop_path = str(directory) if directory else None
    except SafetyError as error:
        desktop_path = "Unavailable: " + str(error)
    parts = [f"You are working with an existing project called Caelestia Dev Manager (version {VERSION}).",
             "Before writing code read:\n" + "\n".join(READ_FIRST),
             "Project directory: " + str(manager.paths.project),
             "Environment (read-only detection):\n" + json.dumps(manager.environment, indent=2),
             "Existing components:\n" + json.dumps(components, indent=2),
             "Component Store publishing target (the desktop UI uses this built-in catalogue):\n" +
             json.dumps({"repository": DEFAULT_REPOSITORY, "branch": "main",
                         "manager_directory": "caelestia-dev-manager/",
                         "published_components": "components/<component-id>/",
                         "local_development_source": str(manager.paths.sources)}, indent=2),
             "Paths:\n" + json.dumps({"source": str(manager.paths.sources), "apps": str(manager.paths.manager / "apps"),
                                         "commands": str(manager.paths.bin), "desktop_entries": str(manager.paths.data / "applications"),
                                         "desktop_shortcuts": desktop_path,
                                         "services": str(manager.paths.config / "systemd/user"),
                                         "plugins": str(manager.paths.config / "caelestia/plugins")}, indent=2),
             "Prefer plugins/<component-id>/ for new source. If the user will paste your answer into Dev Manager, "
             "output one CAELESTIA_DEV_PACKAGE with --- FILE: path --- sections.\n"
             "DO NOT make the new component a page inside Caelestia Dev Manager. It must be independently installable "
             "into its proper runtime environment and must not require Dev Manager to remain open. "
             "Do not modify the production environment when development files can be prepared first.\n"
             "Use UTF-8 source, SVG assets, lowercase hyphenated IDs, relative file paths, semantic versions, "
             "and Python/Qt 6 where appropriate. No arbitrary installer hooks, sudo, broad deletions, traversal or symlinks. "
             "Declare dependencies and permissions. Static validation never executes source.\n"
             "Standalone apps and scripts may optionally set desktop.createShortcut=true (default false). "
             "The manager copies the canonical application launcher to the configured XDG desktop directory, "
             "tracks exact file ownership and offers independent create/remove actions. Never hardcode ~/Desktop "
             "or create a launcher that opens Dev Manager. Services and shell integrations cannot request shortcuts.\n"
             "Caelestia discovery uses metadata.json (type quickshell), main.qml or explicit ui, "
             "under XDG_CONFIG_HOME/caelestia/plugins/<id>. Do not invent dashboard hooks. "
             "KDE integration is reserved until a target adapter is verified. QML components currently support only "
             "integration.target=caelestia-plugin. Manager 0.4 supports the reviewed, checksum-pinned "
             "Cast Audio adapter: id=cast-audio, type=caelestia-plugin, runtime=quickshell, "
             "integration.target=caelestia-quick-toggles. It adds an expandable receiver row, auto-enables new "
             "installs and restarts Caelestia. Updates preserve enabled state; uninstall restores original host files. "
             "Read docs/QUICK_TOGGLES_INTEGRATION.md. Other shell plugins still need explicit reload. "
             "Use saved private device IPs and routed connectivity for VLANs; never promise Google-account "
             "enumeration without a documented Linux API, or collect credentials for an unsupported feature.",
             "DEPENDENCY AND VALIDATION WORKFLOW:\n"
             "Use the inventory's exact validation errors and dependency reports to diagnose failures. "
             "Missing system executable errors mean the tool is absent from the manager's PATH; do not remove a required "
             "dependency or weaken validation to obtain valid=true. System dependencies are executable names, while "
             "Python dependencies are distribution requirements prepared in an isolated component environment. "
             "Manager 0.5 prepares Python dependencies for python/python-pyside6 runtimes and Quickshell sidecars. "
             "A Quickshell helper must launch the installed _venv/bin/python; invoke console tools as Python modules "
             "to avoid staging shebangs. Cast Audio declares catt==0.13.3 there, so installation prepares it automatically. "
             "Its fixed manager recipe can install missing ffmpeg/pactl/parec on Arch/CachyOS or Debian/Ubuntu and prepare "
             "an already-active UFW firewall through reviewed native authentication. Never hardcode a computer address; "
             "select its route to the receiver and use the configured stream port. Other system tools still require "
             "explicit setup. Global pip or the manager environment does not satisfy component dependencies. Keep the shell "
             "activation/restart and source-review warnings; they are expected warnings, not validation errors. Revalidate after fixing "
             "dependencies and report any remaining compatibility or source errors separately.",
             "GITHUB AND STORE DELIVERY WORKFLOW:\n"
             "For a component build or update, prepare the complete store-ready project in addition to local source. "
             "The store discovers only components/<component-id>/manifest.json on the repository's main branch. "
             "Files saved only under this manager's plugins/ directory or on an unmerged branch are not published. "
             "Inspect Git status, repository root, remotes and current published version first. This local project may be "
             "a standalone checkout with no remote; use a separate checkout of the target suite when necessary. "
             "Preserve unrelated changes and existing catalogue components. Keep manager changes under caelestia-dev-manager/ "
             "and publish the component's own complete relative tree under components/<id>/. Bump semantic versions for "
             "published updates and keep Caelestia metadata.json fields in sync with manifest.json. Include README, entrypoint, "
             "all imported local modules, SVG assets, dependency setup and permissions. Exclude virtual environments, caches, "
             "credentials, logs, backups, reference clones, user settings, symlinks, submodules and binary files. "
             "Validate the exact publishing tree with backend.store.checked_files and backend.validators.validate; "
             "distinguish catalogue validity from machine-specific dependency/compatibility readiness. Run relevant tests "
             "using temporary XDG roots. Never execute a component to discover the catalogue.\n"
             "When the current request authorizes GitHub publishing, commit the scoped, reviewed files and push through "
             "existing Git credentials or authenticated gh, without changing global Git settings or force-pushing. "
             "A branch or draft PR is pending until it reaches main. After publishing, perform a fresh Store.scan() in an "
             "isolated cache and verify the expected component ID, version and source_hash against the remote snapshot. "
             "Do not claim publication based on a local commit alone. If publishing is outside the request, prepare the "
             "reviewable files and exact delivery steps. Report repository link, branch/commit, tests, catalogue verification "
             "and any remaining blockers. Users then Refresh the store and review Install/Update; publication does not "
             "install, enable or restart a live component."]
    for doc in ("docs/ARCHITECTURE.md", "docs/COMPONENT_SPEC.md", "docs/CODEX_PACKAGE_FORMAT.md", "docs/CODEX_WORKFLOW.md", "docs/COMPONENT_STORE.md", "docs/QUICK_TOGGLES_INTEGRATION.md"):
        path = manager.paths.project / doc
        if path.exists(): parts.append(f"\n--- {doc} ---\n" + path.read_text())
    parts.append("\nCURRENT REQUEST:\n" + request.strip())
    return "\n\n".join(parts)
