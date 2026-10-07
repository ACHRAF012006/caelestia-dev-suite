"""Memory-only live MP3 fanout on one LAN interface; no remote control API."""
import asyncio
from collections import deque
import secrets
import time
from urllib.parse import urlsplit

from safety import Failure


class Stream:
    def __init__(self, processes, address, receiver):
        self.processes, self.address, self.receiver = processes, address, receiver
        self.path = "/" + secrets.token_hex(24) + "/live.mp3"
        self.server = self.encoder = self.pump = None
        self.queues, self.clients = set(), set()
        self.recent = deque(maxlen=3)
        self.ready = asyncio.Event()
        self.failure = ""
        self.last_audio = time.monotonic()
        self.receiver_reads = 0
        self.url = ""

    async def start(self, monitor, bitrate):
        try:
            self.server = await asyncio.start_server(self.serve, self.address, 0, limit=16384)
            port = self.server.sockets[0].getsockname()[1]
            self.url = f"http://{self.address}:{port}{self.path}"
            self.encoder = await self.processes.spawn([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-f", "pulse", "-i", monitor, "-vn", "-c:a", "libmp3lame",
                "-b:a", f"{bitrate}k", "-ar", "48000", "-ac", "2", "-flush_packets", "1",
                "-write_xing", "0", "-id3v2_version", "0", "-f", "mp3", "pipe:1"], capture=True)
            self.pump = asyncio.create_task(self.read_audio())
            await asyncio.wait_for(self.ready.wait(), 8)
            if self.failure:
                raise Failure(self.failure)
        except TimeoutError:
            raise Failure("Audio source unavailable: FFmpeg did not produce audio") from None

    async def read_audio(self):
        try:
            while block := await self.encoder.stdout.read(4096):
                self.recent.append(block)
                self.last_audio = time.monotonic()
                self.ready.set()
                for queue in tuple(self.queues):
                    if queue.full():
                        # Disconnect slow readers rather than accumulating audio/latency.
                        self.queues.discard(queue)
                        while not queue.empty():
                            queue.get_nowait()
                        queue.put_nowait(None)
                    else:
                        queue.put_nowait(block)
            self.failure = "Stream failed: FFmpeg stopped; check output monitor and libmp3lame support"
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failure = "Stream failed while reading encoded audio"
        finally:
            self.ready.set()
            for queue in tuple(self.queues):
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        if len(self.clients) >= 8:
            writer.close()
            return
        self.clients.add(task)
        queue = None
        try:
            peer = writer.get_extra_info("peername")[0]
            async with asyncio.timeout(5):
                raw = await reader.readuntil(b"\r\n\r\n")
            first = raw.split(b"\r\n", 1)[0].decode("ascii")
            method, target, protocol = first.split(" ")
            if (peer not in (self.receiver, self.address) or urlsplit(target).path != self.path
                    or protocol not in ("HTTP/1.0", "HTTP/1.1")):
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            if method not in ("GET", "HEAD", "OPTIONS"):
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            headers = ("HTTP/1.1 200 OK\r\nContent-Type: audio/mpeg\r\nCache-Control: no-store\r\n"
                       "Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n"
                       "Access-Control-Allow-Headers: Range\r\nConnection: close\r\n")
            if method != "GET":
                writer.write((headers + "Content-Length: 0\r\n\r\n").encode())
                await writer.drain()
                return
            writer.write((headers + "Transfer-Encoding: chunked\r\n\r\n").encode())
            queue = asyncio.Queue(maxsize=32)
            for block in self.recent:
                queue.put_nowait(block)
            self.queues.add(queue)
            while True:
                block = await asyncio.wait_for(queue.get(), 10)
                if block is None:
                    break
                writer.write(f"{len(block):x}\r\n".encode() + block + b"\r\n")
                await asyncio.wait_for(writer.drain(), 3)
                if peer == self.receiver:
                    self.receiver_reads += len(block)
        except (TimeoutError, ValueError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        finally:
            if queue is not None:
                self.queues.discard(queue)
            writer.close()
            self.clients.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        tasks = list(self.clients)
        if self.pump:
            tasks.append(self.pump)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.encoder:
            await self.processes.end(self.encoder)
            self.encoder = None
        self.recent.clear()
        self.queues.clear()
