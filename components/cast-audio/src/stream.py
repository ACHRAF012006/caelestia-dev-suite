"""Memory-only live MP3 fanout on one LAN interface; no remote control API."""
import asyncio
import errno
import fcntl
import os
from collections import deque
import secrets
import socket
import time
from urllib.parse import urlsplit

from safety import Failure


class Stream:
    label = "Live MP3 · receiver delay varies"

    def __init__(self, processes, address, receiver, port=0):
        self.processes, self.address, self.receiver = processes, address, receiver
        self.path = "/" + secrets.token_hex(24) + "/live.mp3"
        self.port = port
        self.server = self.encoder = self.pump = None
        self.capture = None
        self.diagnostics = None
        self.encoder_errors = b''
        self.queues, self.clients = set(), set()
        self.writers = set()
        self.closing = False
        self.close_task = None
        self.recent = deque(maxlen=2)
        self.ready = asyncio.Event()
        self.failure = ""
        self.last_audio = time.monotonic()
        self.receiver_reads = 0
        self.url = ""

    async def start(self, monitor, bitrate):
        try:
            self.server = await asyncio.start_server(self.serve, self.address, self.port, limit=16384)
            port = self.server.sockets[0].getsockname()[1]
            self.port = port
            self.url = f"http://{self.address}:{port}{self.path}"
            self.encoder = await self.encode(monitor, ["-vn", "-c:a", "libmp3lame",
                "-b:a", f"{bitrate}k", "-ar", "48000", "-ac", "2", "-flush_packets", "1",
                "-write_xing", "0", "-id3v2_version", "0", "-f", "mp3", "pipe:1"])
            self.pump = asyncio.create_task(self.read_audio())
            await asyncio.wait_for(self.ready.wait(), 8)
            if self.failure:
                raise Failure(self.failure)
        except TimeoutError:
            raise Failure("Audio source unavailable: FFmpeg did not produce audio") from None
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                raise Failure(f"Audio stream port {self.port} is in use; choose another port in Settings") from None
            raise Failure("Audio stream could not bind the receiver route's local address") from None

    async def encode(self, source, options):
        """App-only Pulse monitor capture through a bounded, owned OS pipe."""
        prefix = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin']
        if not isinstance(source, dict) or source.get('kind') != 'application':
            monitor = source['monitor'] if isinstance(source, dict) else source
            encoder = await self.processes.spawn(prefix + ['-f', 'pulse', '-sample_rate', '48000',
                '-channels', '2', '-fragment_size', '3840', '-probesize', '32', '-analyzeduration', '0',
                '-i', monitor] + options, capture=True, diagnostics=True)
            self.diagnostics = asyncio.create_task(self.read_encoder_errors(encoder))
            return encoder
        index = source.get('stream_index')
        if type(index) is not int or index < 0:
            raise Failure('Invalid application audio stream')
        read_fd, write_fd = os.pipe()
        try:
            # At 48 kHz stereo s16, 4096 bytes is about 21 ms of PCM.
            fcntl.fcntl(write_fd, fcntl.F_SETPIPE_SZ, 4096)
            self.capture = await self.processes.spawn(['parec', '--raw', '--format=s16le',
                '--rate=48000', '--channels=2', '--latency-msec=20', '--process-time-msec=10',
                '--client-name=Cast Audio', '--stream-name=Selected app audio',
                '--device=' + source['monitor'], '--monitor-stream=' + str(index)],
                capture=True, stdout=write_fd)
            os.close(write_fd)
            write_fd = None
            encoder = await self.processes.spawn(prefix + ['-f', 's16le', '-ar', '48000', '-ac', '2',
                '-probesize', '32', '-analyzeduration', '0', '-i', 'pipe:0'] + options,
                capture=True, stdin=read_fd, diagnostics=True)
            self.diagnostics = asyncio.create_task(self.read_encoder_errors(encoder))
            return encoder
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)

    async def read_encoder_errors(self, encoder):
        # Drain stderr continuously so an error pipe cannot block capture.
        # Retain only a bounded tail in memory, never expose raw device/path data.
        while block := await encoder.stderr.read(1024):
            self.encoder_errors = (self.encoder_errors + block)[-4096:]

    def encoder_failure(self, codec):
        errors = self.encoder_errors.lower()
        if b'no space left' in errors:
            return "Live audio memory buffer is full; free memory and retry"
        if b'unknown encoder' in errors or b'encoder not found' in errors:
            return "FFmpeg lacks the " + codec + " encoder; reinstall FFmpeg"
        if any(word in errors for word in (b'no such process', b'no such file', b'connection refused', b'input/output error')):
            return "Audio source unavailable; refresh sources and reconnect"
        return "FFmpeg stopped; refresh the audio source and retry"

    async def read_audio(self):
        try:
            while block := await self.encoder.stdout.read(1024):
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
            self.failure = self.encoder_failure("MP3")
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
        if self.closing or len(self.clients) >= 8:
            writer.close()
            return
        self.clients.add(task)
        self.writers.add(writer)
        queue = None
        try:
            writer.transport.set_write_buffer_limits(high=4096, low=1024)
            writer.get_extra_info("socket").setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
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
            queue = asyncio.Queue(maxsize=6)
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
            if queue is not None:
                # End a live/slow stream without waiting to flush stale audio.
                writer.transport.abort()
            self.writers.discard(writer)
            self.clients.discard(task)

    async def close(self):
        # Share cleanup across Stop, monitor failures and helper shutdown.
        if self.close_task is None:
            self.close_task = asyncio.create_task(self.close_owned())
        try:
            await asyncio.shield(self.close_task)
        except asyncio.CancelledError:
            # Do not let a cancelled Start/watch leave capture running while
            # Stop proceeds with the controller's already-detached stream.
            await self.close_task
            raise

    async def close_owned(self):
        self.closing = True
        server, self.server = self.server, None
        if server:
            server.close()
        # Python 3.12+ Server.wait_closed also waits for client transports.
        # Close live readers before awaiting it, or Stop deadlocks forever.
        for writer in tuple(self.writers):
            writer.transport.abort()
        tasks = list(self.clients)
        if self.pump:
            tasks.append(self.pump)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.diagnostics:
            self.diagnostics.cancel()
            await asyncio.gather(self.diagnostics, return_exceptions=True)
            self.diagnostics = None
        if self.encoder:
            await self.processes.end(self.encoder)
            self.encoder = None
        if self.capture:
            await self.processes.end(self.capture)
            self.capture = None
        if server:
            await server.wait_closed()
        self.encoder_errors = b''
        self.recent.clear()
        self.queues.clear()
