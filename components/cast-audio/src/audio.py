"""Read-only PulseAudio protocol inspection, including PipeWire's pulse server."""
import json
import hashlib

from safety import Failure, text


async def sources(processes):
    try:
        sinks = json.loads(await processes.run(["pactl", "-f", "json", "list", "sinks"]))
        inputs = json.loads(await processes.run(["pactl", "-f", "json", "list", "sources"]))
        default = (await processes.run(["pactl", "get-default-sink"])).strip()
        applications = json.loads(await processes.run(["pactl", "-f", "json", "list", "sink-inputs"]))
        if not isinstance(sinks, list) or not isinstance(inputs, list) or not isinstance(applications, list):
            raise Failure('Audio source unavailable: unexpected audio server response')
        by_index = {s["index"]: s["name"] for s in inputs}
        names = {s["name"] for s in inputs}
        result = []
        for sink in sinks:
            monitor = sink.get("monitor_source_name") or sink.get("monitor_source")
            if type(monitor) is int:
                monitor = by_index.get(monitor)
            if not isinstance(monitor, str) or monitor not in names or len(monitor) > 255:
                continue
            if any(not c.isprintable() for c in monitor):
                continue
            result.append({"id": sink["name"], "name": text(sink.get("description") or sink["name"]),
                           "monitor": monitor, "sink_index": sink.get("index"),
                           "kind": "output", "default": sink["name"] == default})
        if not result:
            raise Failure("Audio source unavailable: no output monitor was found")
        outputs = {item["sink_index"]: item for item in result if type(item["sink_index"]) is int}
        for app in applications[:128]:
            if not isinstance(app, dict):
                continue
            index, props = app.get("index"), app.get("properties", {})
            output = outputs.get(app.get("sink"))
            if not output or type(index) is not int or index < 0 or not isinstance(props, dict):
                continue
            # Include process/serial identity: a reused Pulse index must never
            # silently substitute an unrelated app for the user's selection.
            identity = [str(props.get(key, "")) for key in
                        ("object.serial", "application.process.id", "application.process.binary", "application.name")]
            fingerprint = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            result.append({"id": f"app:{index}:{fingerprint}", "kind": "application",
                           "name": text(props.get("application.name") or props.get("application.process.binary") or "Application"),
                           "detail": text(props.get("media.name") or "Audio stream"),
                           "monitor": output["monitor"], "stream_index": index,
                           "default": False, "playing": not app.get("corked", False)})
        return result
    except (ValueError, KeyError, TypeError):
        raise Failure("Audio source unavailable: unexpected pactl output") from None


def select(items, choice):
    found = next((s for s in items if (s["default"] if choice == "default" else s["id"] == choice)), None)
    if found is None:
        raise Failure("Audio source unavailable; start audio in the selected app or choose another source")
    return found
