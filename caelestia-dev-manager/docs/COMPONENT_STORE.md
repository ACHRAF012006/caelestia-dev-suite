# GitHub component store

The suite repository has two main folders:

    caelestia-dev-manager/       Manager application, docs and installer
    components/
        touchdeck/              Independently installed TouchDeck app
        another-component/      Future reviewed component

Only actual `components/<id>/manifest.json` projects appear as products. The
manager folder's `plugins/` is local development/downloaded source, separate from
the published catalogue. Developer folders beginning with `_` are skipped.

## Browsing and applying updates

Open Component Store, select an app and press Install. The catalogue uses
`https://github.com/ACHRAF012006/caelestia-dev-suite.git` on `main` automatically;
there are no repository or branch fields. Legacy custom repository settings are
ignored by the UI. Startup checks are on by default, asynchronous and cancellable.
Settings disables them; Refresh requests a manual check.

App cards show an icon, description and installation status. Search filters by
name, ID, description and type; All apps, Installed and Updates filter the list.
One main button changes from Install to Update when the published fingerprint
differs, or Open when an installed app can launch. Non-launchable/disabled
components use Components for enablement and runtime actions.

Install/Update downloads an inert, commit-pinned development snapshot and
continues into the existing dependency preparation and installation reviews.
The readable review shows permissions and an optional desktop shortcut;
Show technical details includes exact destination paths, generated launchers,
dependencies and complete component source. More details on an app offers its
permissions, requirements, repository commit and source for advanced inspection.
There is no separate Download Source button or Code tab. Cancelling a review
leaves installed files unchanged; downloaded development source may remain for
retry. Scanning never updates running applications automatically.

After an update, Previous version restores the newest saved installation with a
different payload or version. Same-payload enablement, shortcut and manual
backups are skipped. Review and confirm Restore Version. Your current installation
is backed up first, and your configuration and latest development source are kept.
Close and reopen the app afterward; services need an explicit Start. Further
snapshot selection and reversing a restore are available in Backups. Before the
first update, Previous version is hidden because no earlier payload exists.

An existing local component can be linked to the store when its complete source
matches the published component. Different local source is preserved. After a
store download, manually changed files block further store replacement; reconcile
your edits with the repository before updating. Installation still detects source
changes independently of remote version numbers. A reviewed store update does
not overwrite installed files or their ownership receipts.

## Storage, failures and source recovery

Settings are `$XDG_CONFIG_HOME/caelestia-dev-manager/store.json`. The bare Git
object cache and last catalogue are under
`$XDG_DATA_HOME/caelestia-dev-manager/store/<repository-key>/`. Cache entries are
validated again when loaded. Failed/offline checks leave the last good catalogue
available and report the error inside the store. A new repository/branch uses a
separate cache, so old entries are not presented as belonging to the new source.

Previous source directories are retained under
`$XDG_DATA_HOME/caelestia-dev-manager/source-backups/<uuid>/<id>/`, with adjacent
metadata identifying the original destination, source hash and date. These are
source backups, not the installed-payload backups shown on the Backups page. They
are never automatically deleted. To recover a source swap interrupted by a
process crash, close the manager, inspect metadata, preserve any current source,
and restore the retained directory to the metadata's original source destination.
Then reopen the manager and validate. Installed runtimes remain independent.

Git must be installed by the user. The manager never installs system tools. Only
HTTPS GitHub URLs without embedded credentials are accepted. Private repositories
need an already configured Git credential helper or an authenticated GitHub CLI.
The CLI helper is selected per Git command, without global Git changes; checks do not open interactive
credential prompts or store tokens. Raw Git errors are not logged because they
can contain credentials. Missing Git, inaccessible branches and network failures
disable only repository checking.

## Publishing components

Add `components/<id>/` containing its schema-1 manifest, README, Python/QML/shell
source and SVG assets. Keep dependencies, permissions, semantic version, relative
paths and existing lifecycle rules. Commit and push to the configured branch.
The next startup/manual check discovers the new component or source update.
Do not commit environments, credentials, user configuration, logs, backups or
binary payloads. No installer hooks, symlinks or submodules are allowed in a store
component. Git fetches are bare, with hooks and unsafe transports disabled; source
is read as UTF-8 blobs and Python is parsed, never imported for discovery.

Limits are 128 catalogue components, 500 files and 8 MiB of text per component,
and 64 MiB of total catalogue text. Invalid components are skipped with a reason.
The store does not update the manager itself. Use its GitHub bootstrap installer
or rerun `install.sh` from reviewed manager source to update the manager.

## Cast Audio panel integration

Cast Audio 0.5.0 requires Dev Manager 0.5.1 or newer. Update the manager by rerunning `./install.sh` from current `caelestia-dev-manager/` source (or the suite bootstrap), then Refresh and review the component update. Manager releases are source/installer updates, not component catalogue entries. The reviewed Cast install automatically adds the expandable row, enables new installations and restarts the shell. See [adapter contract](QUICK_TOGGLES_INTEGRATION.md).
