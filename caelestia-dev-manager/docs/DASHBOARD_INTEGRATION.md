# Generic dashboard pages (Dev Manager 0.7.0)

Manager 0.8 routes this existing adapter through the trusted CapabilityRegistry
and central compatibility matrix. Receipt formats and native runtime behavior
remain unchanged. See [ADAPTER_API](ADAPTER_API.md) and [RECOVERY_MODEL](RECOVERY_MODEL.md).

## Verified host, not an upstream registration API

Inspection on 2026-10-09 verified installed Caelestia KDE v2.5.1 and freshly
fetched upstream `main` at `e34b6957fad5ce9395841b65be9e3df180ccd65c`.
PluginLoader creates one object from each enabled plugin's metadata UI. It does
not register dashboard tabs. Content.qml builds five Config-filtered native tabs;
Wrapper.qml owns lazy content and per-monitor ScreenState. The manager's shared
adapter supplies the missing integration. PluginLoader and native tab navigation
remain upstream code. Supporting an upstream registration API later would change
the adapter, rather than every component.

## Contract

A schema-1 `caelestia-plugin`, runtime `quickshell`, may declare:

```json
"integration": {
  "target": "caelestia-dashboard",
  "dashboard": {
    "id": "calendar",
    "title": "Calendar",
    "icon": "calendar_month",
    "component": "DashboardPage.qml",
    "order": 60
  }
}
```

All five dashboard keys are required. IDs use the usual lowercase component-ID
syntax; built-in IDs and `timer` are reserved. IDs must be unique across installed
pages, including disabled pages. Titles contain 1–40 printable characters. Icon
is a Material symbol name, not a resource URL. Component is a relative QML source
path using letters, digits, `_`, `-`, `/` and a `.qml` suffix; it must exist in the
published source. Order is an integer 1–1000, never a boolean. Unknown keys,
absolute paths, traversal, scripts and destinations fail validation. Page ordering
is `(order, page ID, component ID)`, after the Config-filtered native tabs and
legacy Timer. Page ID may differ from component ID.

Declare `compatibility.manager_min_version: "0.7.0"` and the pinned
`compatibility.caelestia_commit`. Supply metadata matching the manifest and your
own static `desktop.icon` asset. This asset is Store identity; `dashboard.icon`
is the native tab's Material symbol. The historical `animated-timer` and
`cast-audio` IDs retain their existing compatibility targets.

The page's root item exports:

```qml
required property var controller
property bool presentationActive: true
implicitWidth: Tokens.sizes.dashboard.mediaTabWidth
implicitHeight: Tokens.sizes.dashboard.mediaTabHeight
```

The manager calculates the installed file URL, supplies the actual
PluginLoader-created object as `controller`, and binds `presentationActive` to
visibility and page identity. Each monitor gets its own page, while the plugin
object owns shared state and sidecars. No manager runtime is needed. The host
container caps page dimensions to the current logical screen; components use
layouts and handle smaller sizes. Components are responsible for a compatible
QML root contract; static validation cannot prove arbitrary QML behavior.

## Ownership and lifecycle

`backend/dashboard_contract.py` validates declarations. The dispatcher routes by
capability. `backend/dashboard_integration.py` owns shared membership and sealed
transactions; `backend/dashboard_compat.py` contains host-version knowledge and
transforms. Components never supply host code. Exact version/commit markers and
both pristine host hashes are required. The only host destinations are
`modules/dashboard/Content.qml` and `modules/dashboard/Wrapper.qml`.

`$XDG_DATA_HOME/caelestia-dev-manager/host-integrations/dashboard-pages.json`
retains pristine originals, modes, membership, Timer participation and expected
host checksums. Every modification starts from verified originals, composing the
entire desired membership deterministically. Host files are separate from
component payload ownership. Adding, updating or removing a page preserves every
other registration. Disabling hides metadata and therefore its tab, but reserves
its ID and retains the shared bridge. Enable/disable verifies dirty-host state.
Native Nexus disabledPlugins remains an additional upstream control.

Install/update plans include exact BEFORE/AFTER source. New installations enable
and reload after the reviewed lifecycle action; updates preserve disabled state.
Uninstall removes only that registration and owned payload. Last-page removal
restores pristine host source, or the Timer-only source if Timer remains. User
component data outside payloads is untouched. Backup/Restore and Previous Version
reconcile the saved manifest against current membership instead of restoring an
obsolete whole-dashboard snapshot that would erase newer pages.

The shared plan, host source and both dashboard/legacy receipts participate in the
existing backup → durable intent → files → registry commit coordinator. Partial
writes or interrupted membership transitions recover the prior state. Recovery
re-derives source from validated declarations; arbitrary journal source is not
accepted. Dirty content, changed modes, corrupt receipts, unsupported versions,
stale preview membership or third-party recovery edits fail closed. There is no
force-overwrite operation. Other host adapters, such as Cast Quick Toggles, remain
independent.

## Timer compatibility

The existing `caelestia-dashboard-timer` manifest and Timer-only adapter/receipt
are unchanged. No Timer component version bump or installed payload rewrite is
required. The first generic page composes existing Timer source into the shared
bridge. Timer remains before generic pages, so its notch index still matches.
Presentation activity uses Timer's ID rather than assuming it is the final tab.
The legacy receipt stays valid for the Timer-only form and is coordinated in the
same transaction. Removing Timer while other pages remain only removes Timer;
removing the last generic page reconstructs the exact legacy form and receipt.
Both installation orders, disabled updates, backup restore and interrupted
composition are tested. Downgrade to pre-0.7 managers only after removing generic
pages with the current manager. Older managers cannot understand shared ownership.

## Testing and adding another host version

Run `.venv/bin/pytest -q` and
`.venv/bin/python scripts/dashboard_qml_probe.py`. The probe copies installed
host source, replaces the copy's dashboard with pinned fixtures, and uses private
XDG roots, D-Bus sessions and two virtual KWin outputs at scale 1.25. It tests
native page loading and Timer routing without patching/restarting production.
The Timer-specific probe remains available for its animation/alarm acceptance.

For a new host version, inspect PluginLoader, Content, Wrapper, ScreenState,
Tabs, sizing, theme and focus behavior at an immutable upstream commit. Add
pristine fixtures and a compatibility implementation in the host layer with exact
hashes and release markers; select supported versions explicitly. Test every
membership/lifecycle/recovery combination and preserve existing receipt versions.
Do not accept fuzzy string matches or bless changed files simply by recomputing a
hash. Host upgrades with active integrations currently require explicit
reconciliation; no automatic rebase of third-party modifications is provided.
