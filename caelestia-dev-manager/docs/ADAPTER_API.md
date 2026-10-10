# Trusted capability / adapter API

`backend.capabilities.CapabilityRegistry` is the closed registry of type installers,
reviewed integration targets and journal proposal IDs. Its immutable mappings hold
manager-owned classes/modules; manifests never provide module names or Python code.
`backend.host_integration` remains the public compatibility facade. Cast source is
now `quick_toggle_integration`; existing receipt identity/version and transforms
are retained. Shared dashboard routing takes precedence over Timer-only routing.
Adding a reviewed host adapter requires registering it here, a compatibility rule,
strict manifest validation, fixtures and lifecycle/recovery tests.

Type installers generate FilePlans and UI action capabilities. The manager retains
ownership, lifecycle, backups, restore and transaction coordination. Host modules
implement requested, plan, check, apply, recover, receipt_path and read_receipt.
Plans expose exact BEFORE/AFTER, modes and receipt transitions. check re-derives
trusted outputs and verifies fresh host/receipt state. apply uses atomic writes.
recover validates derivation and accepts only before/after states; third-party
edits block rollback. Adapters cannot expand generic payload destination roots.

| Capability | Destinations / dependencies | Enable/disable, update/uninstall, restore/health | Limitations |
| --- | --- | --- | --- |
| application / script | Fixed payload, user launcher; optional exact desktop shortcut; declared executable/private Python requirements | Launcher mode/desktop visibility; owned-file replacement/removal; verified backup restore; hashes and process identity | Detached runtime; runtime permissions are disclosures, not a sandbox |
| service | Fixed payload and exact cdm-ID user unit; private requirements | User systemd enable/disable/start/stop; stop before replacement; explicit restart after restore; unit state | systemd state external to file transaction |
| caelestia-plugin / qml-component | Fixed user plugin root, discovery metadata, quickshell and declared sidecars | Metadata rename; explicit shell reload; verified hashes; independent real shell lifetime | QML runtime health cannot be queried per component |
| quick-toggle | Two exact utilities/Nexus files; Cast only; reviewed fixed machine setup | Fixed transform + receipt; update preserves disabled state; uninstall restores originals; journals and health verify files/modes | Reviewed signatures, no arbitrary patches |
| caelestia-dashboard / Timer | Two dashboard files; strict page declaration; legacy Timer composition | Membership-based update/restore/removal; preserve other pages; hide disabled discovery; exact host receipt checks | v2.5.1 only; no generic upstream registration API |
| desktop-shortcut | Canonical launcher copied to approved XDG desktop path | Exact checksum/mode ownership, complete snapshot backup, independent toggle | Apps/scripts only; collision refused |
| KDE integration | None | No actions | Reserved until a reviewed adapter exists |

`backend.compatibility.HOST_RULES` records release, immutable commit, adapter
revision and exact file checksums. Timer/shared dashboard require both release
markers plus signatures. Cast permits an unmarked host only with its verified
signature (including reviewed legacy migration); a declared unknown release is
unsupported. Diagnostic statuses distinguish Verified, Compatible by verified
signature, Unsupported, Host modified and Adapter update required. Receipt-derived
expected transformed signatures are accepted only after receipt validation.
Structural loader detection remains a discovery check, not host-write authority.
Future versions require new reviewed rules and fixtures; never auto-bless a release.
