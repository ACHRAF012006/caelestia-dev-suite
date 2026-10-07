"""Verified catt 0.13.2+ CLI; all device commands use discovered literal IPs."""
import json
import re
import socket
import uuid

from safety import Failure, local_ip, text


def decode(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise Failure("Unexpected catt response; catt 0.13.2 or newer is required") from None


def devices(raw):
    result = []
    for item in list(decode(raw).values())[:128]:
        if not isinstance(item, dict):
            continue
        try:
            identity = str(uuid.UUID(str(item.get("uuid", ""))))
            host = local_ip(item.get("host", ""))
        except (ValueError, Failure):
            continue
        supported = item.get("port") == 8009
        result.append({"id": identity, "host": host, "name": text(item.get("friendly_name") or host),
                       "supported": supported,
                       "detail": text(item.get("model_name", "")) if supported else "Nonstandard Cast port/group is unsupported by this CLI adapter"})
    return sorted(result, key=lambda d: d["name"].casefold())


def route(host):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((local_ip(host), 8009))
        return local_ip(sock.getsockname()[0])


class Cast:
    def __init__(self, processes):
        self.processes = processes

    async def check(self):
        output = await self.processes.run(["catt", "--version"])
        match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", output)
        if not match or tuple(map(int, match.groups())) < (0, 13, 2):
            raise Failure("catt 0.13.2 or newer is required")

    async def scan(self, timeout):
        await self.check()
        try:
            return devices(await self.processes.run(["catt", "scan", "--json-output"], timeout))
        except Failure as exc:
            raise Failure("Discovery unavailable; check mDNS/firewall. " + str(exc)) from None

    async def command(self, receiver, *args, timeout=12):
        return await self.processes.run(["catt", "--device", local_ip(receiver["host"]), *args], timeout)

    async def info(self, receiver):
        info = decode(await self.command(receiver, "info", "--json-output"))
        if not info or "app_id" not in info:
            raise Failure("Speaker unreachable or status unavailable")
        return info

    @staticmethod
    def busy(info):
        app = info.get("app_id")
        return (info.get("player_state") not in (None, "UNKNOWN", "IDLE") or
                app not in (None, "", "E8C28D3C", "CC1AD845"))

    async def start(self, receiver, url):
        if self.busy(await self.info(receiver)):
            raise Failure("Receiver already busy; stop its current session before casting")
        await self.command(receiver, "cast", "--force-default", "--no-subs", "--no-playlist",
                           "--stream-type", "LIVE", "--title", "Caelestia system audio", url, timeout=35)

    async def stop_owned(self, receiver, url):
        # Never quit another controller's replacement media deliberately.
        if (await self.info(receiver)).get("content_id") == url:
            await self.command(receiver, "stop")
