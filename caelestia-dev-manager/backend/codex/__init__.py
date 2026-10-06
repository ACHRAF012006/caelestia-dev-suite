import json
from pathlib import Path
from backend.paths import VERSION
from backend.desktop import desktop_directory
from backend.paths import SafetyError

READ_FIRST = ["PROJECT_CONTEXT.md", "README.md", "docs/ARCHITECTURE.md", "docs/PLUGIN_SPEC.md",
              "docs/COMPONENT_SPEC.md", "docs/CODEX_PACKAGE_FORMAT.md", "docs/CODEX_WORKFLOW.md"]

def context(manager, request):
    components = [{"id": r["id"], "type": r["manifest"]["type"], "version": r["manifest"]["version"],
                   "installed": r.get("installed", False), "enabled": r.get("enabled", False),
                   "status": r["status"], "source": str(manager.paths.source(r["id"])),
                   "desktop_shortcut_created": r["desktop_shortcut_created"],
                   "desktop_shortcut_path": (r.get("desktop_shortcut") or {}).get("path")} for r in manager.all_status()]
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
             "integration.target=caelestia-plugin. Reload requires an explicit systemctl --user restart caelestia-shell.service."]
    for doc in ("docs/ARCHITECTURE.md", "docs/COMPONENT_SPEC.md", "docs/CODEX_PACKAGE_FORMAT.md", "docs/CODEX_WORKFLOW.md"):
        path = manager.paths.project / doc
        if path.exists(): parts.append(f"\n--- {doc} ---\n" + path.read_text())
    parts.append("\nCURRENT REQUEST:\n" + request.strip())
    return "\n\n".join(parts)
