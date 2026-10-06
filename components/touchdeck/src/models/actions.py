import shlex
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox
from models.config import uid, validate_action


class Actions(QObject):
    """Known actions only. Macros await each step; no imported runtime code."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pending = {}
        self.busy = False
        window.audio.completed.connect(self._completed)
        window.media.completed.connect(self._completed)

    def _completed(self, token, ok, message):
        callback = self.pending.pop(token, None)
        if callback:
            callback(ok, message)
        elif message and (not ok or "muted" in message):
            self.window.toast(message)

    def _request(self, service, operation, value, done):
        token = uid()
        self.pending[token] = done
        service.request(operation, value, token)
        QTimer.singleShot(10000, lambda: self._completed(token, False, "Action timed out") if token in self.pending else None)

    def execute(self, action):
        if self.busy:
            self.window.toast("An action is running; use Cancel action to stop remaining macro steps")
            return
        try:
            validate_action(action)
        except ValueError as error:
            self.window.toast(str(error))
            return
        self.busy = True
        self.generation = uid()
        generation = self.generation
        steps = list(action["steps"]) if action["type"] == "macro" else [action]
        def next_step(ok=True, message=""):
            if generation != self.generation:
                return
            if not ok or not steps:
                self.busy = False
                self.window.toast(message or "Action completed")
                return
            step = steps.pop(0)
            QTimer.singleShot(step.get("delay_ms", 0), lambda: self._step(step, next_step) if generation == self.generation else None)
        next_step()

    def cancel(self):
        self.generation = uid()
        self.busy = False
        self.window.toast("Remaining macro steps cancelled; submitted actions keep running")

    def _step(self, action, done):
        window, kind = self.window, action["type"]
        value = action.get("value", "")
        try:
            if kind == "launch":
                done(True, window.apps.launch(value) + " launched")
            elif kind in ("url", "file"):
                if kind == "url":
                    url = QUrl(value)
                    if not url.isValid() or url.scheme() not in ("https", "http", "mailto"):
                        raise ValueError("Only http, https and mailto URLs are supported")
                else:
                    path = Path(value).expanduser()
                    if not path.is_absolute() or not path.exists():
                        raise ValueError("File or folder unavailable")
                    url = QUrl.fromLocalFile(str(path))
                done(QDesktopServices.openUrl(url), "Open requested")
            elif kind == "command":
                argv = action["argv"]
                if QMessageBox.question(window, "Run advanced command?", shlex.join(argv), QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                    done(False, "Command cancelled")
                    return
                process = QProcess(self)
                process.setStandardOutputFile(QProcess.nullDevice())
                process.setStandardErrorFile(QProcess.nullDevice())
                finished = [False]
                def complete(ok):
                    if not finished[0]:
                        finished[0] = True
                        done(ok, "Command finished" if ok else "Command failed")
                        process.deleteLater()
                process.finished.connect(lambda code, status: complete(code == 0 and status == QProcess.NormalExit))
                process.errorOccurred.connect(lambda error: complete(False) if error == QProcess.FailedToStart else None)
                process.start(argv[0], argv[1:])
            elif kind == "media":
                player, _ = window.media.selected(window.config.data)
                self._request(window.media, "media", {"player": player, "method": value}, done)
            elif kind == "audio":
                target = "input" if value == "mic_mute" else "output"
                operation = "volume" if value == "volume" else "mute"
                payload = {"kind": target}
                if operation == "volume":
                    payload["level"] = action["level"] / 100
                self._request(window.audio, operation, payload, done)
            elif kind == "profile":
                profile = window.config.data["profiles"].get(value)
                if profile is None:
                    raise ValueError("Audio profile unavailable")
                self._request(window.audio, "profile", profile, done)
            elif kind == "system":
                if value != "lock":
                    prompt = value.title() + "?"
                    if value == "logout":
                        prompt += "\nThis terminates the session. Save your work first."
                    if QMessageBox.question(window, prompt, prompt, QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
                        done(False, "Session action cancelled")
                        return
                self._request(window.media, "power", value, done)
            elif kind == "page":
                if not window.switch_page(value):
                    raise ValueError("Page unavailable")
                done(True, "Page opened")
            elif kind == "settings":
                window.open_settings()
                done(True, "Settings saved")
            else:
                raise ValueError("Unsupported action")
        except (OSError, ValueError, KeyError) as error:
            done(False, str(error))
