# Notes & Tasks 0.2.0

A native Caelestia KDE dashboard page, requiring Dev Manager 0.7.0+ and verified
Caelestia KDE v2.5.1 (`e34b6957fad5ce9395841b65be9e3df180ccd65c`). Install from the
Component Store after updating the manager; review the shared dashboard plan.
Publishing does not install, enable or reload anything on your desktop.

Use the capture card or **+** to write a note; choose **Task** in the expanded
card for a task. Enter or Ctrl+Enter saves immediately. A captured note opens in
its inline editor, with the body focused. Ctrl+N captures a note, Ctrl+Shift+N a
task, Ctrl+F expands search, and Escape closes secondary controls when the shell
grants keyboard focus. Ctrl+Enter finishes an inline note edit.

The page is a collection of shell-themed widgets: a large capture surface, a
virtualized paper-card grid, a Today completion ring and task list, and clickable
tag pills. Pinned cards have a subtle accent shape. Different card heights sit
inside stable grid cells; there is no custom masonry engine. On narrow pages the
widgets stack in a scrollable composition; each collection also scrolls
independently. All/Notes/Tasks pills can devote space to one section. Search starts
as an icon and expands while focused or containing text. It debounces for 100 ms
and reconciles matching model rows without clearing the whole model.

Notes have optional titles/tags, plain-text bodies, timestamps, pinning, archives,
duplication, search and deletion. Pinned notes sort first; archives stay out of the
default view. Edit directly in the dashboard; changes save after a 650 ms pause,
with a three-second maximum delay during continuous typing. The page reports pending saves and errors.

Tasks support title, details, tags, completion/uncompletion, permanent deletion,
manual up/down ordering, optional local due date/time and priority, and editable
subtasks. Expand Details & properties for advanced fields. Open tasks groups
Today (including overdue), Upcoming and Anytime. Today, Upcoming, Completed and
All Tasks filters are available; All Tasks includes completed items. Completion
is retained indefinitely. Completion writes immediately; visible rows fade and
finish their ring transition before their filter membership/order changes after
at most 180 ms. Completing again quickly interrupts the previous presentation
state. The Done filter permits uncompletion. Manual ordering applies within date sections; changing
the sort in Settings does not erase manual order. Date/time are organizational
metadata in this version, not scheduled reminders.

Search checks note title/body, task title/details/subtasks and tags in memory.
Settings offers default section, completed visibility, note/task sorting, compact
cards, animation preference and delete confirmation. Reduced animation disables
component-owned transitions. Shell duration tokens are respected and component
motion is capped at 150–200 ms; global shell tab animations remain shell settings.
Decorative paper/ink details respond to interaction and never loop while idle.
All monitors share one PluginLoader controller and one exclusive storage writer.
Each page keeps its own search and editor selection.

## Storage and backup

Data lives at `$XDG_DATA_HOME/caelestia-components/notes-tasks/`, defaulting to
`~/.local/share/caelestia-components/notes-tasks/`:

- `data.json`: versioned UTF-8 notes, tasks and preferences.
- `data.previous.json`: the previous known-good committed document.
- `writer.lock`: an advisory lock preventing simultaneous writers.

Writes use a private temporary file, fsync, atomic replacement and directory
fsync. Disable/update/uninstall never remove this directory. Manager payload
backups and Previous Version do **not** back up personal notes/tasks. Include this
entire directory in your normal personal-data backups. The retained previous
snapshot helps with a recent bad edit; it is not a history or external backup.
Before manual recovery, unload the plugin/stop its helper, preserve both files,
inspect the previous JSON and restore it only after checking its contents.

Malformed or unknown-newer data opens in an error state and is never replaced by
empty data. Unsupported older versions require an explicit migration. Save errors
or external edits stop writing until resolved and the shell is reloaded. The UI
reports the error; pending edits acknowledged before a failed disk write may
remain only in memory, so preserve their text before reloading.

## Architecture and extension points

`main.qml` owns the helper and controller signals. `models/FilteredModel.qml`
maintains incremental sorted/filter models; GridView virtualizes fixed-size note
cells containing differently sized cards, and ListView virtualizes task rows.
`components/` separates controls, grids, editors, capture, search, tags, progress,
paper marks, empty states and settings. Shared shell StyledRect, StyledText,
MaterialIcon, Anim and CircularProgress primitives supply the visual language. `helper/domain.py` validates field-level operations and produces DTOs;
`helper/storage.py` handles schemas and persistence; `helper/main.py` serializes
commands and debounces saves without idle polling. See [SCHEMA.md](SCHEMA.md) and
[TESTING.md](TESTING.md). The manager's generic contract is documented in
`caelestia-dev-manager/docs/DASHBOARD_INTEGRATION.md` in the suite repository.

Note content has a format envelope; records retain extension maps. Tasks reserve
recurrence and project IDs. These allow later Markdown, folders, projects,
attachments, calendars, encryption and synchronization to be designed without
coupling the UI to raw storage. The storage schema and Python helper are unchanged from 0.1.0; this release needs
no data migration. Version 0.2.0 does not implement those future features,
cloud sync, notifications or reminders.
