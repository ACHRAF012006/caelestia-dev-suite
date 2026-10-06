import configparser
import locale
import os
import shutil
from pathlib import Path
from PySide6.QtCore import QProcess
from utils.paths import root


class Applications:
    def __init__(self):
        self.apps = {}
        self.refresh()

    def refresh(self):
        apps, seen = {}, set()
        languages = [locale.getlocale()[0] or "", os.environ.get("LANG", "").split(".")[0]]
        languages += [x.split("_")[0] for x in languages]
        desktops = set(os.environ.get("XDG_CURRENT_DESKTOP", "KDE").split(":"))
        directories = [root("DATA"), *map(Path, os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"))]
        for directory in directories:
            base = directory / "applications"
            for path in sorted(base.rglob("*.desktop")) if base.is_dir() else []:
                ident = str(path.relative_to(base)).replace("/", "-")
                if ident in seen:
                    continue
                seen.add(ident)
                try:
                    parser = configparser.ConfigParser(interpolation=None, strict=False)
                    parser.optionxform = str
                    parser.read(path, encoding="utf-8")
                    entry = parser["Desktop Entry"]
                    if entry.get("Type") != "Application" or any(entry.get(k, "false").lower() == "true" for k in ("Hidden", "NoDisplay")):
                        continue
                    only = set(filter(None, entry.get("OnlyShowIn", "").split(";")))
                    exclude = set(filter(None, entry.get("NotShowIn", "").split(";")))
                    if (only and not only & desktops) or exclude & desktops:
                        continue
                    if entry.get("TryExec") and not shutil.which(entry["TryExec"]):
                        continue
                    def localized(key):
                        return next((entry[key + "[" + lang + "]"] for lang in languages if key + "[" + lang + "]" in entry), entry.get(key, ""))
                    apps[ident] = {"id": ident, "name": localized("Name") or ident,
                                   "description": localized("Comment"), "icon": entry.get("Icon", ""), "path": str(path)}
                except (OSError, UnicodeError, configparser.Error):
                    continue
        self.apps = apps

    def launch(self, ident):
        item = self.apps.get(ident)
        if not item or not Path(item["path"]).is_file():
            raise ValueError("Application unavailable; edit or remove this launcher")
        ok, _ = QProcess.startDetached(shutil.which("gio") or "gio", ["launch", item["path"]])
        if not ok:
            raise ValueError("Application launcher failed")
        return item["name"]
