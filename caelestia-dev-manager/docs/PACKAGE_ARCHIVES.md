# Portable component packages

`.cdmpkg` is a ZIP containing `package.json` (format=1, kind=component, component
ID/version and complete size/SHA-256 inventory) and regular files under `payload/`.
The original manifest is included. Transport is inert: no trusted installation
scripts, environment payloads or execution. Existing install.sh/setup.py source,
if included, remains inert source and is never invoked as a hook.

Import bounds compressed archive to 32 MiB, payload to 16 MiB, individual files to
8 MiB, metadata to 512 KiB and files to 500. Metadata is inspected before staging;
paths must be safe relative paths. Duplicate paths, traversal, backslashes, Windows
drive paths, hidden/cache paths, links, directories, device/FIFO/socket modes,
set-ID bits, encrypted/nonstandard compression and extra link metadata are refused.
The inventory must match every archive member exactly. Extraction uses explicit
regular-file writes into a private temporary stage, never extractall. CRC, declared
size, SHA-256, strict manifest, static source and resource checks are verified.
Staging is removed afterward. Qt Import Package displays text source and binary
size/hash metadata, then offers Create Source only. Installation always uses the
existing reviewed transaction flow; extraction never installs or launches code.

Export Package on Components writes a new file; existing destinations are refused.
It transfers development source/resources, not personal data, absolute ownership
receipts, generated launchers, machine-specific environments or credentials.
Text paste packages remain UTF-8 and cannot encode binary resources.

Schema 2 `resources` maps binary filenames to exact sha256 and MIME descriptors.
Images (PNG/JPEG/WebP/GIF/ICO), audio (WAV/MP3/Ogg/FLAC), fonts (TTF/OTF/WOFF/WOFF2)
and arbitrary declared inert bytes are supported. Known extension MIME and simple
magic signatures must agree. Text/code stays UTF-8 without NUL. Import does not
decode images/fonts/audio, render thumbnails or execute resources. Existing safe
static SVG preview remains independent. Source readers reject special files.
Binary content is copied byte-for-byte at non-executable source modes.
