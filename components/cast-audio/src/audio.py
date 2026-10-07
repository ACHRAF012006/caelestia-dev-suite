"""Read-only PulseAudio protocol inspection, including PipeWire's pulse server."""
import json

from safety import Failure, text


async def sources(processes):
    try:
        sinks = json.loads(await processes.run(["pactl", "-f", "json", "list", "sinks"]))
        inputs = json.loads(await processes.run(["pactl", "-f", "json", "list", "sources"]))
        default = (await processes.run(["pactl", "get-default-sink"])).strip()
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
                           "monitor": monitor, "default": sink["name"] == default})
        if not result:
            raise Failure("Audio source unavailable: no output monitor was found")
        return result
    except (ValueError, KeyError, TypeError):
        raise Failure("Audio source unavailable: unexpected pactl output") from None


def select(items, choice):
    found = next((s for s in items if (s["default"] if choice == "default" else s["id"] == choice)), None)
    if found is None:
        raise Failure("Audio source unavailable; select an available output monitor")
    return found
