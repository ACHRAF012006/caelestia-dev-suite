"""Bounded AAC/HLS live audio on private Linux tmpfs; no disk fallback."""
import asyncio
from collections import OrderedDict
import errno
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import urlsplit

from safety import Failure, no_links
from stream import Stream

SEGMENT = re.compile(r"segment-[0-9]{1,20}\.ts")


def memory_root():
    # Refuse a disk-backed /dev/shm rather than silently recording audio there.
    root = no_links(Path('/dev/shm'))
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    if not any(line.split(' - ')[0].split()[4] == str(root) and
               line.split(' - ')[1].split()[0] == 'tmpfs' for line in mounts):
        raise Failure('Live mode needs Linux /dev/shm tmpfs; choose MP3 in Settings')
    return root


def reap_abandoned(root):
    """Remove only this user's dead helper sessions, never an active sender."""
    for folder in root.glob(f'cast-audio-{os.getuid()}-*'):
        match = re.fullmatch(rf'cast-audio-{os.getuid()}-([0-9]+)-[a-z0-9_]+', folder.name)
        if not match or folder.is_symlink() or not folder.is_dir() or folder.stat().st_uid != os.getuid():
            continue
        try:
            os.kill(int(match[1]), 0)
            continue
        except ProcessLookupError:
            pass
        except PermissionError:
            continue
        children = list(folder.iterdir())
        if any(child.is_symlink() or not child.is_file() or child.stat().st_uid != os.getuid() or
               not (child.name in {'live.m3u8', 'live.m3u8.tmp'} or SEGMENT.fullmatch(child.name.removesuffix('.tmp')))
               for child in children):
            continue
        for child in children:
            child.unlink(missing_ok=True)
        folder.rmdir()


class HlsStream(Stream):
    label = 'Live AAC · 0.5 s segments · receiver delay varies'

    def __init__(self, *args, latency='balanced', **kwargs):
        super().__init__(*args, **kwargs)
        self.segment_time = .125 if latency == 'fast' else .5
        self.window_size = 24 if latency == 'fast' else 12
        self.label = 'Live AAC · ' + ('fast' if latency == 'fast' else 'balanced') + ' · receiver delay varies'
        self.path = self.path.replace('live.mp3', 'live.m3u8')
        self.prefix = self.path.rsplit('/', 1)[0] + '/'
        self.directory = None
        self.playlist = b''
        self.raw_playlist = b''
        self.segments = OrderedDict()

    async def start(self, monitor, bitrate):
        try:
            root = memory_root()
            reap_abandoned(root)
            self.directory = Path(tempfile.mkdtemp(prefix=f'cast-audio-{os.getuid()}-{os.getpid()}-', dir=root))
            self.server = await asyncio.start_server(self.serve, self.address, self.port, limit=16384)
            self.port = self.server.sockets[0].getsockname()[1]
            self.url = f'http://{self.address}:{self.port}{self.path}'
            self.encoder = await self.encode(monitor, [
                '-vn', '-c:a', 'aac', '-b:a', f'{bitrate}k', '-ar', '48000', '-ac', '2',
                '-f', 'hls', '-hls_time', str(self.segment_time), '-hls_list_size', str(self.window_size), '-hls_delete_threshold', '4',
                '-hls_flags', 'delete_segments+omit_endlist+independent_segments+temp_file+program_date_time',
                '-hls_segment_options', 'mpegts_copyts=1',
                '-hls_segment_filename', str(self.directory/'segment-%d.ts'), str(self.directory/'live.m3u8')])
            self.pump = asyncio.create_task(self.refresh_audio())
            await self.wait_ready()
            if self.failure:
                raise Failure(self.failure)
        except TimeoutError:
            raise Failure('No live audio from the selected source. Resume playback or choose another source and retry.') from None
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                raise Failure(f'Audio stream port {self.port} is in use; choose another port in Settings') from None
            raise Failure('Live stream could not create its private memory buffer or bind the receiver route') from None

    async def wait_ready(self):
        # Allow a slow but progressing encoder to fill its live window. Do not
        # extend the deadline indefinitely when an input stops delivering PCM.
        deadline = time.monotonic() + 20
        while not self.ready.is_set():
            try:
                await asyncio.wait_for(self.ready.wait(), 1)
            except TimeoutError:
                if time.monotonic() >= deadline or time.monotonic() - self.last_audio > 12:
                    raise TimeoutError from None

    def read_snapshot(self):
        try:
            self.read_complete_snapshot()
        except FileNotFoundError:
            # FFmpeg atomically replaces the playlist and deletes old segments
            # concurrently. Keep the last complete snapshot and retry next tick;
            # never publish a partial cache or count the race as fresh audio.
            return

    def read_complete_snapshot(self):
        path = no_links(self.directory/'live.m3u8')
        if not path.exists():
            return
        if path.stat().st_size > 16384:
            raise Failure('Live playlist exceeded its size limit')
        playlist = path.read_bytes()
        if playlist == self.raw_playlist:
            return
        lines = playlist.decode('ascii').splitlines()
        names = [line for line in lines if line and not line.startswith('#')]
        if not lines or lines[0] != '#EXTM3U' or not 1 <= len(names) <= self.window_size or any(not SEGMENT.fullmatch(name) for name in names):
            raise Failure('Invalid live audio playlist')
        updated = {}
        for name in names:
            if name in self.segments:
                continue
            segment = no_links(self.directory/name)
            if segment.stat().st_size > 262144:
                raise Failure('Live audio segment exceeded its size limit')
            updated[name] = segment.read_bytes()
        # Publish atomically after every referenced completed file is available.
        self.segments.update(updated)
        while len(self.segments) > self.window_size * 2:
            self.segments.popitem(last=False)
        self.raw_playlist = playlist
        # FFmpeg rounds subsecond durations to an integer. A zero target is
        # invalid HLS and can make receivers spin or reject the live playlist.
        self.playlist = re.sub(rb'(?m)^#EXT-X-TARGETDURATION:0$', b'#EXT-X-TARGETDURATION:1', playlist)
        self.last_audio = time.monotonic()
        # Give the receiver enough history to select a stable live position.
        if len(names) >= self.window_size:
            self.ready.set()

    async def refresh_audio(self):
        try:
            while self.encoder.returncode is None:
                self.read_snapshot()
                await asyncio.sleep(.1)
            self.failure = self.encoder_failure('AAC')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = str(error) if isinstance(error, Failure) else 'Stream failed while preparing live audio'
        finally:
            self.ready.set()

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        if self.closing or len(self.clients) >= 8:
            writer.close()
            return
        self.clients.add(task)
        self.writers.add(writer)
        try:
            peer = writer.get_extra_info('peername')[0]
            async with asyncio.timeout(5):
                raw = await reader.readuntil(b'\r\n\r\n')
            method, target, protocol = raw.split(b'\r\n', 1)[0].decode('ascii').split(' ')
            path = urlsplit(target).path
            name = path[len(self.prefix):] if path.startswith(self.prefix) else ''
            manifest = path == self.path
            body = self.playlist if manifest else self.segments.get(name) if SEGMENT.fullmatch(name) else None
            code = '200 OK'
            if peer not in (self.receiver, self.address) or protocol not in ('HTTP/1.0', 'HTTP/1.1') or body is None or not body:
                code, body = '404 Not Found', b''
            elif method not in ('GET', 'HEAD', 'OPTIONS'):
                code, body = '405 Method Not Allowed', b''
            mime = 'application/vnd.apple.mpegurl' if manifest else 'video/mp2t'
            headers = (f'HTTP/1.1 {code}\r\nContent-Type: {mime}\r\nContent-Length: {len(body) if method != "OPTIONS" else 0}\r\n'
                       'Cache-Control: no-store\r\nAccess-Control-Allow-Origin: *\r\n'
                       'Access-Control-Allow-Methods: GET, HEAD, OPTIONS\r\nAccess-Control-Allow-Headers: Range\r\nConnection: close\r\n\r\n')
            writer.write(headers.encode())
            if method == 'GET':
                writer.write(body)
            await asyncio.wait_for(writer.drain(), 3)
            if peer == self.receiver and method == 'GET' and not manifest and code == '200 OK':
                self.receiver_reads += len(body)
        except (TimeoutError, ValueError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            pass
        finally:
            writer.close()
            # Keep the writer tracked until finite responses finish flushing.
            try:
                await asyncio.wait_for(writer.wait_closed(), 3)
            except (TimeoutError, OSError):
                writer.transport.abort()
            finally:
                self.writers.discard(writer)
                self.clients.discard(task)

    async def close_owned(self):
        try:
            await super().close_owned()
        finally:
            self.playlist = b''
            self.raw_playlist = b''
            self.segments.clear()
            if self.directory:
                shutil.rmtree(self.directory)
                self.directory = None
