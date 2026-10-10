import json
import re
from dataclasses import dataclass
from backend.paths import SafetyError, relative
from backend.validators import manifest_parse

@dataclass
class Package:
    files: dict
    headers: dict

    def tree(self):
        return "\n".join("  " + name for name in sorted(self.files))

def parse(text, filename="src/main.py"):
    if len(text.encode()) > 8 * 1024 * 1024: raise SafetyError("Package exceeds 8 MiB")
    text = text.replace("\r\n", "\n")
    # A single outer Markdown fence is tolerated; per-file fences are literal content.
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```") and lines[-1] == "```":
        text = "\n".join(lines[1:-1])
    markers = list(re.finditer(r"^--- FILE: (.+?) ---[ \t]*$", text, re.MULTILINE))
    files, headers = {}, {}
    if not markers:
        if text.lstrip().startswith("CAELESTIA_DEV_PACKAGE"): raise SafetyError("Structured package has no FILE sections")
        files[str(relative(filename))] = text
        return Package(files, headers)
    preamble = text[:markers[0].start()].strip()
    if preamble:
        lines = preamble.splitlines()
        if lines[0] != "CAELESTIA_DEV_PACKAGE": raise SafetyError("Unexpected content before FILE sections")
        for line in lines[1:]:
            if not line.strip(): continue
            k, sep, v = line.partition(":")
            if not sep or k not in {"name", "id", "type", "version", "description"} or k in headers:
                raise SafetyError(f"Invalid package header: {line}")
            headers[k] = v.strip()
    for i, match in enumerate(markers):
        path = str(relative(match.group(1)))
        if path in files: raise SafetyError(f"Duplicate file: {path}")
        end = markers[i+1].start() if i+1 < len(markers) else len(text)
        files[path] = text[match.end():end].removeprefix("\n")
    if len(files) > 500: raise SafetyError("Package exceeds 500 files")
    for path in files:
        if any(other.startswith(path + "/") for other in files): raise SafetyError(f"File/directory conflict: {path}")
    if "manifest.json" in files:
        m = manifest_parse(files["manifest.json"])
        for k, v in headers.items():
            if k in m and m[k] != v: raise SafetyError(f"Package header {k} conflicts with manifest")
    return Package(files, headers)

def detect(text):
    if re.search(r"\bimport (QtQuick|Quickshell)\b", text): return "quickshell" if "Quickshell" in text else "qml"
    if text.startswith("#!") and re.search(r"(?:bash|/sh)\b", text.splitlines()[0]): return "shell"
    if "PySide6" in text: return "python-pyside6"
    if re.search(r"^(import |from |def |class )", text, re.MULTILINE): return "python"
    return "none"

def encode(files, manifest):
    if any(isinstance(value, bytes) for value in files.values()):
        raise SafetyError('Binary resources need .cdmpkg archive transport; paste packages remain UTF-8')
    header = "CAELESTIA_DEV_PACKAGE\n" + "\n".join(f"{k}: {manifest[k]}" for k in ("name", "id", "type", "version"))
    return header + "\n\n" + "\n".join(f"--- FILE: {p} ---\n{value.rstrip()}\n" for p, value in files.items())
