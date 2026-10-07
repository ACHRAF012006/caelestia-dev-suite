# Codex workflow

In **Codex Context**, enter the request and select **Copy Full Codex Prompt**. The resulting prompt contains read-first project files, actual read-only desktop/shell detection, manager version, component inventory, enabled state, paths, architecture, manifest contract, package framing and the current request.

The UI uses its latest inspection snapshot when generating this prompt so opening the tab does not repeat installed-file hashing. Refresh component information first when you need newly changed runtime/source state. While the initial inspection is loading, prompt generation shows a loading message and Copy leaves the clipboard unchanged.

Future Codex sessions must read PROJECT_CONTEXT.md, README.md, docs/ARCHITECTURE.md, docs/PLUGIN_SPEC.md, docs/COMPONENT_SPEC.md, docs/CODEX_PACKAGE_FORMAT.md and this document. Create source under `plugins/<component-id>/`. If the user wants copy/paste output, use `CAELESTIA_DEV_PACKAGE`.

Never make a new component a runtime page inside Dev Manager. Never require Dev Manager to remain open. Never directly modify production when source and an installation plan can be prepared first. Inspect installed Caelestia and current upstream before assuming integration paths or APIs. For a dashboard request, explain the verified limitations and design a supported integration or propose a separate upstream hook for review.

The user pastes the returned package into Create / Import, checks Files/Manifest/Destination/Validation, saves development source, edits/tests it as appropriate, and reviews Install. Standalone apps then appear in KDE as their own entries. Services become user units; shell plugins become actual Caelestia components after activation/reload. Source changes produce Update Available; they do not mutate live code.

Declare dependencies and permissions. No arbitrary install hooks, broad file deletions, symlinks, traversal, global Python modifications or sudo. Tests for destructive actions use temporary XDG roots. Components should write user data to their own XDG data/state paths, rather than modifying manager-owned executable files.
