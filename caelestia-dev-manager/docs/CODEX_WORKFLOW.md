# Codex workflow

In **Codex Context**, enter the request and select **Copy Full Codex Prompt**. Completed code tasks include scoped Git commits and pushes by default; state any repository/branch constraints or an explicit exception in the request. The resulting prompt contains read-first project files, actual read-only desktop/shell detection, manager version, component inventory, enabled state, paths, architecture, manifest contract, package framing and the current request. It also includes declared dependencies, cached dependency reports, exact validation errors/warnings, source fingerprints, installed versions, store provenance and the GitHub publishing target.

The UI uses its latest inspection snapshot when generating this prompt so opening the tab does not repeat installed-file hashing. Refresh component information first when you need newly changed runtime/source state. While the initial inspection is loading, prompt generation shows a loading message and Copy leaves the clipboard unchanged.

Future Codex sessions must read PROJECT_CONTEXT.md, README.md, docs/ARCHITECTURE.md, docs/PLUGIN_SPEC.md, docs/COMPONENT_SPEC.md, docs/CODEX_PACKAGE_FORMAT.md, docs/COMPONENT_STORE.md docs/ANIMATED_TIMER_INTEGRATION.md, docs/DASHBOARD_INTEGRATION.md and this document. Create source under `plugins/<component-id>/`. If the user wants copy/paste output, use `CAELESTIA_DEV_PACKAGE`.

Never make a new component a runtime page inside Dev Manager. Never require Dev Manager to remain open. Never directly modify production when source and an installation plan can be prepared first. Inspect installed Caelestia and current upstream before assuming integration paths or APIs. For a dashboard request, explain the verified limitations and design a supported integration or propose a separate upstream hook for review.

The user pastes the returned package into Create / Import, checks Files/Manifest/Destination/Validation, saves development source, edits/tests it as appropriate, and reviews Install. Standalone apps then appear in KDE as their own entries. Services become user units; shell plugins become actual Caelestia components after activation/reload. Source changes produce Update Available; they do not mutate live code.

Declare dependencies and permissions. No arbitrary install hooks, broad file deletions, symlinks, traversal, global Python modifications or sudo. Tests for destructive actions use temporary XDG roots. Components should write user data to their own XDG data/state paths, rather than modifying manager-owned executable files.

## Resolve dependencies before delivery

Missing executable errors are real installation blockers. Keep required tools in the manifest and verify them on the manager's PATH and, for shell plugins, the service's PATH. Manager 0.5 prepares private Python distributions for Python runtimes and Quickshell sidecars. Launch sidecars with installed `_venv/bin/python` and invoke Python-backed tools as modules, avoiding staging shebangs. Cast Audio declares `catt==0.13.3`; Install prepares it automatically. Its fixed manager recipe reviews missing ffmpeg/pactl/parec packages on supported systems and incoming TCP rules on an already-active UFW firewall using native administrator authentication. Do not hardcode any development computer address or run component-supplied privileged hooks. Revalidate after setup. Source-review warnings remain visible. General plugins need explicit restart; Cast Audio uses the manager-owned automatic adapter.

## Deliver to the GitHub store

The desktop store reads `https://github.com/ACHRAF012006/caelestia-dev-suite.git`, branch `main`. Local `plugins/<id>/` source is not a catalogue entry. Prepare the complete component under the suite's `components/<id>/`; manager changes belong under `caelestia-dev-manager/`. Read [the publishing contract](COMPONENT_STORE.md#publishing-components) included in the generated prompt.

Inspect the checkout, remotes, current published version and unrelated work before editing. Use a separate suite checkout when the local manager has no remote. Bump versions for published updates, synchronize Caelestia host metadata and include all referenced source/assets and dependency instructions. Validate the exact publishable file mapping using `backend.store.checked_files(files, id)` and `backend.validators.validate(files, manifest, environment)`. Catalogue validity does not establish that every client has the required tools or compatible shell.

Always commit and push completed task changes using existing credentials, without force pushes or global Git changes, unless the current request explicitly overrides this preference. Stage only reviewed task-owned paths/hunks and verify the remote branch/commit. If authentication, missing repository details or branch protection blocks the push, retain the work and report the exact blocker. A branch or PR does not become discoverable until merged into `main`. Verify the final remote snapshot through a fresh `Store.scan()` with an isolated cache, checking ID, version and `source_hash`. Report the repository link and commit plus test/scan results; surface authentication or branch-protection blockers honestly. A pushed feature branch is not published in the Store until merged into main; report that distinction. Preparing files or making a local commit alone does not satisfy Git delivery. Users Refresh the store and review Install/Update afterward; publishing itself never modifies a running component.

## Quick Toggles and receiver settings

Read [Quick Toggles integration](QUICK_TOGGLES_INTEGRATION.md). Cast Audio has its own approved automatic Quick Toggles adapter. Dashboard components use the shared declarative capability in manager 0.7.0 and later; read DASHBOARD_INTEGRATION.md. Animated Timer retains its legacy target and notch; read ANIMATED_TIMER_INTEGRATION.md for that target. It places receivers in a separate expandable row and opens only its advanced Settings in a separate app. Do not invent a plugin registration API or execute supplied patch files. Preserve host edits, seal preview state and include the host plan in recovery. Saved private IPv4 receivers and fixed stream ports support routed VLANs; installation prepares active-UFW rules, while router policies remain separate. Google Home APIs document Android/iOS SDKs; do not create a fake Linux sign-in or claim account-based Cast discovery.

## Component identity and completion

Give each new component its own static `assets/icon.svg`, declared through
`desktop.icon` for any type. This field alone never creates a shortcut. Components
and the Store share a renderer that rejects active SVG and external resources;
known apps have bundled identity icons and other apps get a stable ID-based
monogram. Prompt generation uses the inspected snapshot without rescanning source
or running Git/network commands; the receiving coding agent inspects Git before
edits, completes meaningful checks, and performs the required scoped push.

## Adding future dashboard components

Declare `integration.target = caelestia-dashboard` and the strict page descriptor
in COMPONENT_SPEC and DASHBOARD_INTEGRATION. Build the component/controller; do
not copy Timer's host adapter or add ID-specific manager branches. Current support
is checksum-pinned Caelestia KDE v2.5.1. New host support belongs in the
compatibility layer and its fixtures/tests. Test membership composition, dirty
files, both Timer installation orders, rollback and personal-data survival under
isolated XDG roots. Run the copied-shell dashboard QML probe. Publish complete
`components/<id>/` and changed manager source in `caelestia-dev-manager/`, validate
the exact tree, push scoped changes and verify a fresh main Store scan. Production
installation and reload stay separate from publishing.
