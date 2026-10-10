# Codex package format

Output one UTF-8 package with this exact framing:

```text
CAELESTIA_DEV_PACKAGE
name: Quick Utility
id: quick-utility
type: standalone-app
version: 0.1.0

--- FILE: manifest.json ---
{"id":"quick-utility","name":"Quick Utility","version":"0.1.0","description":"Example","type":"standalone-app","runtime":"python","entrypoint":"src/main.py"}

--- FILE: src/main.py ---
print("Independent utility")

--- FILE: README.md ---
# Quick Utility
Review source before installing.
```

Recognized optional headers: name, id, type, version, description. Duplicate/unknown headers are errors. Header values must match a supplied manifest. Each file marker is a complete line `--- FILE: <safe-relative-path> ---`. Lines after it, until the next marker, are literal file content. A marker line cannot occur literally within a file. Whitespace between sections is preserved as trailing content. CRLF becomes LF; a single outer Markdown fence may be stripped; individual-file fences are not stripped. Do not wrap each file in separate code fences or add prose to the package.

Plain multi-file paste without the `CAELESTIA_DEV_PACKAGE` header is supported using the same file markers. A plain single-source paste is saved with the single-file destination entered in the UI; the manager detects a likely language and generates a manifest using form fields. If a package includes manifest.json, that manifest is authoritative; edit it in the paste editor to change metadata. For missing manifests, fill name/ID/type and inspect the generated preview.

Paths cannot be absolute, traverse parents, contain backslashes/control characters, use empty/dot path segments, or address hidden/cache directories. Duplicate filenames and file/directory prefix collisions are rejected. Maximum pasted package: 8 MiB, 500 files; development source limit: 16 MiB. This paste format supports text assets; SVG is preferred. Binary source/resources use the separately validated .cdmpkg archive format or folder import (PACKAGE_ARCHIVES). A manifest is required before source creation. Save as Draft still requires valid metadata and safe paths but permits missing entrypoints or incomplete code.

Analyze, Preview and Validate never execute source or install anything. Create writes only the development repository. Installation is a separate exact-path review and confirmation.
