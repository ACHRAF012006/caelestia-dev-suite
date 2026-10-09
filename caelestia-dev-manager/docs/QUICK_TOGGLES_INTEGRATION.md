# Verified automatic Cast Audio Quick Toggles adapter

Manager 0.4 introduced the scoped automatic Cast Audio host integration: component ID `cast-audio`, type `caelestia-plugin`, runtime `quickshell`, integration target `caelestia-quick-toggles`. This is a manager-owned adapter, not a public Caelestia registration API or permission for component-supplied patches.

It supports verified Caelestia KDE commit `e34b6957fad5ce9395841b65be9e3df180ccd65c`. Only `modules/utilities/cards/Toggles.qml` and `modules/nexus/pages/utilities/QuickTogglesPage.qml` beneath the detected shell root can change. Pristine input must match pinned checksums; the exact previous Cast 0.1.1 icon layout is recognized for migration. Other content blocks installation.

The fixed transformation adds a full-width expandable receiver Component below existing toggle buttons, reads actual loaded plugins and adds Nexus visibility. Settings opens separately. It does not modify PluginLoader, dashboard tabs or generic allowed destination roots. No plugin patch or installer code is executed.

Installation review shows complete before/after source and the automatic enable/restart behavior. New installs are enabled; updates preserve disabled state. The private host-integrations/cast-audio.json receipt under manager XDG data stores originals, modes, adapter version and expected resulting checksums. It is separate from component payload ownership, so ordinary uninstall cannot delete host files. Receipt originals/checksums are revalidated.

The sealed preview records exact host content and receipt state. Transaction intents include host changes alongside payload and registry changes. A failed/aborted transaction recovers both host files and the previous receipt. Third-party edits encountered during recovery are preserved and require reconciliation. Updates/removal also refuse later content or mode changes.

After successful installation, enable/disable, restore or uninstall, the manager restarts `caelestia-shell.service` through its existing user-service runtime. If restart fails, installed state remains recorded with Reload Required; inspect Logs and retry Settings → Reload Caelestia. This service restart is authorized by the reviewed lifecycle action, not repeated as an extra confirmation. Uninstall restores pristine host originals and retains user preferences. Manager removal itself does not remove components or their integration receipts.

General shell plugins retain explicit enable/reload behavior. The adapter does not grant arbitrary KDE/KWin integrations or general dashboard injection. When upstream files change, verify the new contract and release a compatible manager before applying a new adapter.

Tests use pinned GPL-3.0-only host fixtures under temporary XDG roots, cover install/update/disable/uninstall/restore and failure recovery, and never patch production as a test. Authorized desktop deployment is a separate lifecycle operation.

Manager 0.6.0 adds an independent [Timer dashboard adapter](ANIMATED_TIMER_INTEGRATION.md). It never reuses Cast Audio host files, transforms or receipts. Cast lifecycle behavior remains unchanged.
