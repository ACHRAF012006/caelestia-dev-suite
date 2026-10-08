"""Bounded child: load only this component's private live manifest, then exit."""
import re
import sys
import threading
from urllib.parse import urlsplit

from safety import Failure, local_ip


def checked_url(value):
    parts = urlsplit(value)
    if (parts.scheme != 'http' or parts.username or parts.password or parts.query or parts.fragment or
            not parts.hostname or not parts.port or not 1024 <= parts.port <= 65535 or
            not re.fullmatch(r'/[0-9a-f]{48}/live\.m3u8', parts.path)):
        raise Failure('Invalid live stream URL')
    local_ip(parts.hostname)
    return value


def load(host, url):
    from catt.discovery import get_cast_with_ip
    from cast import Cast
    host, url = local_ip(host), checked_url(url)
    cast = get_cast_with_ip(host)
    if cast is None:
        raise Failure('Speaker unavailable')
    try:
        # Backdrop has no media namespace to answer GET_STATUS. Query it only
        # when the default media app is already running.
        if cast.status.app_id == 'CC1AD845':
            complete = threading.Event()
            cast.media_controller.update_status(callback_function=lambda *_: complete.set())
            if not complete.wait(3):
                raise Failure('Receiver status unavailable')
        status = cast.media_controller.status
        if Cast.busy({'app_id':cast.status.app_id, 'player_state':status.player_state}):
            raise Failure('Receiver already busy')
        cast.media_controller.play_media(url, 'application/vnd.apple.mpegurl',
            title='Caelestia system audio', stream_type='LIVE')
        import time
        deadline = time.monotonic() + 8
        while cast.media_controller.status.content_id != url and time.monotonic() < deadline:
            time.sleep(.05)
        if cast.media_controller.status.content_id != url:
            raise Failure('Receiver did not accept live audio')
    finally:
        cast.disconnect(timeout=3)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise Failure('Invalid live stream command')
        load(sys.argv[1], sys.argv[2])
    except Exception:
        # Never print the private stream token, device status or captured audio.
        raise SystemExit('Live receiver load failed') from None
    print('Live receiver accepted audio')
