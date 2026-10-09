# Architecture

## Boundaries

Qt Widgets (`app/main.py`) presents Dashboard, Components, Create / Import, Codex Context, Backups, Logs, Settings and Component Store. Source editing uses the user's external editor via Open Source; there is no Code page. `app/review.py` shows plain-language installation/restore summaries with exact technical plans on demand. The UI calls `backend.manager.Manager`; component source never becomes a manager page or is imported into the manager interpreter.

The registry is `$XDG_STATE_HOME/caelestia-dev-manager/registry.sqlite3` with component records, a uniquely indexed absolute-path ownership table, and lifecycle events. Records preserve source and installed manifests separately, installed version, source fingerprint, destination, enabled state, timestamps, last operation ID, reload requirement, source deletion history, optional approved desktop-shortcut descriptor and installed shortcut preference. Runtime status also reports shortcut existence, missing/changed files, source availability, service state and best-effort PIDs.

Navigation reuses the current display snapshot instead of repeating environment commands, source validation, installed-file hashes and backup checks for every tab. `app/inspection.py` captures registry records/ownership receipts on the main thread into a read-only inventory, then inspects files, dependencies and runtime state in a worker with its own Runtime. No SQLite connection crosses threads and no component source is executed. Startup and manual Refresh use this worker; navigation requests a background refresh when the snapshot is older than 30 seconds. Repeated requests coalesce, failures retain the prior display, and generations reject results from before a reviewed mutation. Immediate post-mutation refresh remains synchronous. Cancel between files/components and wait for workers to finish when closing; never terminate a thread mid-read.

`Backups.catalog` reads compact display metadata without opening backup blobs. Its records supply labels and previous-version availability only; `read`, `plan_restore` and `restore` still validate every checksum and owned path before applying changes. Component selection, store cards and Codex Context reuse snapshot diagnostics/fingerprints. Display data never substitutes for fresh lifecycle plans or dependency preparation checks.

`app/navigation.py` switches the actual page immediately and fades a mouse-transparent snapshot of the outgoing page for 140 ms. Only the temporary overlay has a graphics effect. The navigation list keeps native keyboard/mouse selection while a single mouse-transparent highlight moves behind transparent text labels for 180 ms. Rapid switches start the highlight from its current position; resize, scroll, hiding and closing stop motion and align it with the selected row. Settings disables both transitions; the preference is stored in XDG manager `settings.json` while retaining existing preference keys.

`app/branding.py` loads the bundled `app/assets/icon.svg` directly, with literal colors rather than symbolic theme colors. Package data includes the asset in wheels and source archives. The manager installer copies the same SVG into its owned manager root, records it in the separate manager receipt and uses its absolute path in the desktop entry. Updates preserve component files; uninstall removes only the recorded logo and other owned manager files. Components' declared SVGs likewise use absolute installed paths in both canonical desktop entries and optional desktop copies.

Source snapshots are UTF-8 file maps under `<development-repository>/plugins/<id>/`. Installed snapshots are at fixed user destinations. Fingerprints include content and filenames, so added, removed or changed source yields Update Available even if the version number was not changed.

## Adapters and capabilities

`backend/installers/` contains BaseInstaller, StandaloneAppInstaller, ScriptInstaller, UserServiceInstaller, CaelestiaPluginInstaller and reserved KDEIntegrationInstaller. These produce sealed FilePlans: target, content or staged source, checksum and mode. Adapter capabilities tell the UI which operations apply. The coordinator implements install/update, uninstall, enable/disable, backup/restore and status; Runtime implements launch/stop/restart/logs. A component cannot supply an arbitrary destination or installation command.

| Type | Installed runtime | Activation |
| --- | --- | --- |
| standalone-app | XDG data `caelestia-dev-manager/apps/<id>/`; user command and `.desktop` | launcher executable; desktop visible |
| script | Same app payload root; user command | launcher executable |
| user-service | Same payload root; `cdm-<id>.service` in XDG config `systemd/user/` | explicit `systemctl --user enable --now` |
| caelestia-plugin | XDG config `caelestia/plugins/<id>/` | discovery metadata plus explicit shell reload |
| qml-component | Only verified Caelestia plugin target | same as Caelestia plugin |
| kde-integration | Reserved | installation rejected |

Generated app launchers invoke an absolute runtime interpreter, installed entrypoint, and manifest args after changing to the installed directory. They contain no manager imports. Popen uses a detached session and closed descriptors. Desktop launcher execution works with the manager entirely absent. PID matching checks the interpreter executable and entrypoint argument prefix, so unrelated programs merely mentioning installed files are excluded. Python dependencies are copied from a prepared component virtual environment into the installed `_venv`; the generated launcher uses that installed interpreter with bytecode writes disabled. Binaries and library files of the environment are owned just like source files. Sources cannot supply `_venv` files.

`backend/desktop.py` reads the XDG desktop configuration without shell evaluation and validates shortcut basenames/descriptors. Manager exposes `plan_create_desktop_shortcut`, `create_desktop_shortcut`, `plan_remove_desktop_shortcut`, `remove_desktop_shortcut` and `has_desktop_shortcut`. Only standalone apps and scripts support these operations. A single canonical `.desktop` entry supplies both launcher locations. Toggle transactions retain existing ownership receipts and never rewrite the payload. Enable/disable and source updates regenerate both launcher copies consistently. Exact recorded shortcut paths remain authorized for removal/restore even if the user's XDG desktop location changes; no broad desktop directory ownership is granted.

## Dependency diagnostics

`backend/dependencies.py` reads `.dist-info/METADATA` as inert text and compares declared requirements using the manager's `packaging` dependency. It never imports a component or launches its interpreter during inspection, and checks source-preparation and installed environments independently. The Components view provides an offline Dependencies report and identifies missing system executables, absent Python distributions, version mismatches and incomplete preparation. A successful receipt alone does not make missing or mismatched distribution metadata ready.

Reviewed preparation captures subprocess stdout/stderr for environment creation and binary-wheel pip resolution. Failure raises a structured `DependencyError`, preserves a bounded, URL-redacted `dependency-error.json` beside the private prepared environment and logs the diagnostic against the component. Network/index failures are distinguished from wheel availability; unknown failures do not guess a package. No install plan follows failed preparation. Retry reuses checked private staging files without recursive deletion, verifies declared distribution metadata and clears the failure only after success. The manifest schema and installed ownership rules are unchanged.

## File operations

`backend/store.py` reads a configured HTTPS GitHub repository's `components/<id>/` tree at an immutable fetched commit. A bare cache under XDG data avoids checkouts, executable filters and component hooks. Symlink/submodule modes, unsafe paths, binary payloads, reserved dependency directories, mismatching manifests and oversized catalogues are rejected. `app/store.py` runs cancellable Git checks on a worker thread; SQLite and UI changes stay in the main thread. The startup scan can be disabled and is skipped in sandbox mode. Failed checks keep the last validated catalogue.

The store UI uses the built-in suite repository and main branch; no repository fields are shown. One primary button chooses Install, Update or Open based on the installed fingerprint and launch capability. Install/Update downloads inert source, then continues into the existing dependency and installation reviews. Store source download plans seal the previous source hash and registry record. Existing local IDs can be linked only if their file contents match the repository. Subsequent store updates refuse modified local source. A download stages inert files, retains the entire previous source directory in XDG data `source-backups/<uuid>/<id>/`, then swaps the source directory and records repository/commit/hash provenance. Errors restore the previous directory; a process crash during the source swap can require restoring the retained source directory manually. These source backups are distinct from installed-payload backups. No download prepares dependencies, modifies ownership receipts or installs code. Cancelling installation can leave downloaded development source, while installed files remain unchanged.

Previous version selects the newest installed backup with a differing installed version or source fingerprint. Same-payload manual, shortcut and enablement snapshots are skipped. It uses the existing reviewed restore transaction, preserving current development source and its store provenance. A fresh pre-restore backup supports undo through Backups. Runtime user configuration outside owned payloads is preserved; service restart remains explicit.

All source paths are relative, all IDs constrained, and all destination paths are canonical children of known per-type roots. Symlink traversal is refused. Previews display exact planned destination paths and executable modes. A source/dependency fingerprint is checked again when applying a preview. Unowned existing files and cross-component ownership collisions fail closed. Modification of an installed file blocks replacement/deletion until reviewed and resolved. Extra files within a payload directory are not owned and are left alone.

Operations take an advisory cross-process flock. Installed-file operations first snapshot all touched files and write a durable intent journal, then atomically replace individual files and commit the new SQLite record/receipt. A journal is removed only after commit. Errors roll files back; after a crash Settings offers recovery. Operation IDs distinguish a completed SQLite commit from an interrupted file phase. This is recoverable coordination, not a single atomic transaction across SQLite, files and systemd. A process crash can require explicit recovery. Systemd enablement/start state is external; inspect it after errors/restores. Updates stop services before replacing their source; starting again is explicit.

Partial shortcut operations also back up the complete previous installed ownership snapshot, so restoring a toggle backup preserves the rest of the app. Backup metadata separately records newly approved shortcut paths needed to roll back creation, without marking that shortcut as present in the prior component record.

Backups are immutable snapshot directories under XDG data `caelestia-dev-manager/backups/<uuid>/` with version, manager version, date, original paths, file modes/checksums and prior record. Restoring checks every blob, refuses unowned collisions, creates a new pre-restore backup and adjusts receipts. Source files remain separate. Empty payload directories are removed only with `rmdir`; recursive installation-directory deletion is never used.

## Caelestia

The installed loader contract is inspected before planning plugin installs. A new plugin is installed with owned `metadata.json.disabled`, so it does not execute during install. Enabling restores `metadata.json`; disabling hides discovery metadata. Existing objects continue until the user explicitly reloads `caelestia-shell.service`. Pending reloads are displayed; loaded/healthy QML state cannot be queried per component through the inspected IPC. Nexus can also disable plugins with its own Qt Settings; manager discovery enablement does not override that separate state. Shell logs determine actual plugin load success.

## Extending the platform

Add manifest fields with strict validation, a target-specific adapter, supported capabilities and isolated safety tests. Document the verified host discovery/activation contract before supporting a new runtime. General KWin or Plasma widgets should use official KDE mechanisms in their own adapter. Dashboard tabs require an upstream hook or reviewed host changes; manager 0.6.0 implements only the fixed Timer-specific adapter.

## Manager-owned Quick Toggles integration (0.4)

`backend/host_integration.py` implements the fixed Cast Audio-only adapter. Host plans are sealed independently of payload FilePlans and stored in the same durable transaction intent. Private receipts retain verified originals and installed hashes. Generic component destinations are unchanged. See [adapter contract](QUICK_TOGGLES_INTEGRATION.md) for automatic enable/restart, edit protection and recovery.

## Cast Audio machine preparation and Quickshell sidecars (0.5)

`backend/system_setup.py` owns fixed audio-package and active-UFW recipes. Component source cannot specify privileged commands. UI reviews preparation before Python dependencies and payload planning; Manager rechecks the current recipe before native pkexec authentication. Only ffmpeg/pactl/parec mappings are automatic on supported distributions; host prerequisites remain explicit. UFW rules use private source ranges, the saved fixed port and any local destination. No computer address is persisted in the recipe. Preparation is external machine state, separate from recoverable user-file transactions, and may remain after cancellation/uninstall. Inactive firewalls are preserved.

Quickshell sidecars may declare Python dependencies. Prepared environments are sealed and copied into the normal component-owned `_venv`, with metadata inspection and lifecycle ownership unchanged. The component must launch its installed interpreter and use modules for console tools because copied console scripts can retain staging shebangs. Cast Audio supplies a bounded launcher for its two sidecars.

## Manager-owned Timer dashboard integration (0.6.0)

`backend/timer_integration.py` pins two dashboard files and release markers, supplying only the Animated Timer bridge. `host_integration.py` dispatches each component to its independent adapter; Timer never uses Cast transformations or receipts. Exact review, sealed plans, journal recovery and lifecycle reloads use the existing coordinator. See [Timer integration](ANIMATED_TIMER_INTEGRATION.md).

## Component identity and generated tasks (0.6.1)

Status inspection includes bounded static icon text from the declared desktop.icon
or conventional assets/icon.svg. This display-only snapshot is never used to
authorize a lifecycle action. The shared app/component_icons.py renderer rejects
active or external SVG references, caches up to 128 pixmaps, respects display
scaling, and supplies bundled known identities or ID-based monograms. Components
and Store use this renderer; tab navigation does not reread source.

backend/codex emits a task-first prompt, current adapter contracts, snapshot
diagnostics, a verification/delivery checklist and required scoped Git delivery.
Generating/copying a prompt never performs Git writes or a network operation.
The receiving agent must verify its remote push and protect unrelated work;
publication remains separate from reviewed runtime installation.

## Shared dashboard capability (0.7.0)

`caelestia-dashboard` is a declarative capability for any compatible Quickshell
plugin. `backend/dashboard_contract.py` validates page identity, title, Material
icon, relative component and order. `backend/dashboard_integration.py` owns shared
membership and receipt transactions; `backend/dashboard_compat.py` isolates
v2.5.1-specific host knowledge. No component can provide patches or host paths.
The shared receipt composes all installed pages deterministically, preserves
Timer's legacy manifest and notch, and participates in existing sealed
backup/journal/recovery operations. Disable retains registration and hides the
loaded page; uninstall/restore change only that component's membership. Host
checksums and release markers remain fail-closed. Read
[DASHBOARD_INTEGRATION.md](DASHBOARD_INTEGRATION.md) for the full contract,
Timer composition, downgrade constraints and adding another supported version.

Notes & Tasks is an independent published component, not a manager page. Its
PluginLoader singleton controller owns one standard-library storage helper;
per-monitor pages share command/delta models. Personal data is under XDG data
`caelestia-components/notes-tasks`, outside payload and manager ownership.
