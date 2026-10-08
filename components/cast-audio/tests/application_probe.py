"""Native app isolation test on an owned silent sink; no user audio is read."""
import asyncio
import array
import math
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import audio
from processes import Processes
from safety import Preferences
from stream import Stream


async def main():
    processes = Processes(Preferences())
    name = 'cast_probe_' + secrets.token_hex(8)
    module = None
    stream = Stream(processes, '127.0.0.1', '127.0.0.1')
    try:
        module = (await processes.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=' + name,
                                      'sink_properties=device.description=Cast_isolation_test'])).strip()
        for frequency in (440, 880):
            await processes.spawn(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
                '-re', '-f', 'lavfi', '-i', f'sine=frequency={frequency}:sample_rate=48000',
                '-ac', '2', '-f', 'pulse', '-name', 'Cast isolation test',
                '-stream_name', str(frequency), '-device', name, '-'], capture=True)
        await asyncio.sleep(1)
        choices = await audio.sources(processes)
        selected = next(item for item in choices if item.get('detail') == '440' and item['monitor'] == name + '.monitor')
        # Exercise the component's real per-app capture/FFmpeg OS pipe.
        stream.encoder = await stream.encode(selected, ['-f', 's16le', '-acodec', 'pcm_s16le', 'pipe:1'])
        data = await asyncio.wait_for(stream.encoder.stdout.readexactly(48000 * 4), 5)
        samples = array.array('h', data)[::2]
        if sys.byteorder != 'little':
            samples.byteswap()
        def energy(frequency):
            return abs(sum(sample * complex(math.cos(2 * math.pi * frequency * n / 48000),
                                             math.sin(2 * math.pi * frequency * n / 48000))
                           for n, sample in enumerate(samples)))
        wanted, excluded = energy(440), energy(880)
        if wanted < 1000 or excluded > wanted * .02:
            raise RuntimeError('Application capture did not isolate the selected stream')
        print('PASS: selected app captured; second app excluded; no playback routing changed.')
    finally:
        await stream.close()
        await processes.close()
        if module:
            await processes.run(['pactl', 'unload-module', module])
        await processes.close()


asyncio.run(main())
