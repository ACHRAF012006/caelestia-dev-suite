"""Bounded asynchronous commands and cancellation of exact owned children."""
import asyncio
import importlib.util
import os
from pathlib import Path
import shutil
import sys

from safety import Failure


class Processes:
    def __init__(self, prefs):
        self.children = set()
        self.environment = dict(os.environ)
        self.environment.update(XDG_CONFIG_HOME=str(prefs.catt_config),
                                XDG_CACHE_HOME=str(prefs.catt_cache),
                                NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            self.environment.pop(name, None)
        self.environment.update(NO_PROXY="*", no_proxy="*")

    async def spawn(self, args, capture=False, *, stdin=asyncio.subprocess.DEVNULL, stdout=None, diagnostics=False):
        cast_command = args[0] in ("catt", "cast-live")
        # Installed console scripts retain staging shebangs; invoke the module
        # with this sidecar's relocated environment instead.
        if args[0] == "cast-live":
            args = [sys.executable, "-B", str(Path(__file__).with_name("cast_live.py")), *args[1:]]
        elif cast_command and importlib.util.find_spec("catt") is not None:
            args = [sys.executable, "-m", "catt.cli", *args[1:]]
        executable = shutil.which(args[0])
        if executable is None:
            raise Failure(args[0] + " unavailable; install this declared dependency manually")
        pending = asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, "-B", str(Path(__file__).with_name("child.py")),
            str(os.getpid()), executable, *args[1:],
            stdin=stdin, stdout=asyncio.subprocess.PIPE if stdout is None else stdout,
            stderr=asyncio.subprocess.DEVNULL if capture and not diagnostics else asyncio.subprocess.PIPE,
            env=self.environment if cast_command else None, limit=65536))
        try:
            process = await asyncio.shield(pending)
        except asyncio.CancelledError:
            process = await pending
            self.children.add(process)
            await self.end(process)
            raise
        self.children.add(process)
        return process

    async def end(self, process):
        async def drain(reader):
            if reader:
                while await reader.read(8192):
                    pass
        drains = [asyncio.create_task(drain(reader)) for reader in (process.stdout, process.stderr)]
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        await process.wait()
        await asyncio.gather(*drains, return_exceptions=True)
        self.children.discard(process)

    async def run(self, args, timeout=12):
        process = await self.spawn(args)

        async def bounded(reader):
            chunks, size = [], 0
            while chunk := await reader.read(8192):
                size += len(chunk)
                if size > 512000:
                    raise Failure(args[0] + " returned too much data")
                chunks.append(chunk)
            return b"".join(chunks)

        tasks = [asyncio.create_task(bounded(process.stdout)), asyncio.create_task(bounded(process.stderr))]
        try:
            async with asyncio.timeout(timeout):
                out, _ = await asyncio.gather(*tasks)
                code = await process.wait()
            if code:
                raise Failure(args[0] + " failed; check dependency, receiver and network availability")
            return out.decode("utf-8", errors="replace")
        except TimeoutError:
            raise Failure(args[0] + " timed out; check the receiver, firewall and network isolation") from None
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.end(process)

    async def close(self):
        for process in list(self.children):
            await self.end(process)
