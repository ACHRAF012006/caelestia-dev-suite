"""Separate settings app bridge. Never starts audio capture or executes a shell."""
import json
import socket
import sys

from safety import Failure, Preferences, no_links


def request(message):
    prefs = Preferences()
    if not isinstance(message, dict) or message.get("action") not in {"get", "settings"}:
        raise Failure("Invalid settings request")
    endpoint = no_links(prefs.runtime / "settings.sock")
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(4)
            connection.connect(str(endpoint))
            connection.sendall(json.dumps(message).encode() + b"\n")
            with connection.makefile("rb") as stream:
                raw = stream.readline(65537)
            if len(raw) > 65536:
                raise Failure("Settings response too large")
            return json.loads(raw)
    except (FileNotFoundError, ConnectionRefusedError):
        # Allows editing preferences while the shell plugin is disabled.
        if message["action"] == "settings":
            changes = message.get("values")
            if not isinstance(changes, dict) or set(changes) - (set(Preferences.defaults) - {"last"}):
                raise Failure("Invalid settings")
            prefs.save(changes)
        return {"ok": True, "snapshot": {"state": "Off", "message": "Settings saved for the next shell load", "settings": prefs.values, "sources": []}}


if __name__ == "__main__":
    for line in sys.stdin:
        try:
            if len(line) > 16384:
                raise Failure("Settings request too large")
            message = json.loads(line)
            result = request(message)
            result["action"] = message.get("action")
        except (Failure, ValueError, OSError) as error:
            result = {"ok": False, "error": str(error)[:240]}
        print(json.dumps(result), flush=True)
