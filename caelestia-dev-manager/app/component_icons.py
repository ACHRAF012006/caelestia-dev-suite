"""Shared static component artwork; untrusted SVG never loads external resources."""
from collections import OrderedDict
import hashlib
from html import escape
from pathlib import Path
import re
from xml.etree import ElementTree

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / 'assets'
BUILTIN = {'cast-audio': 'cast-audio.svg', 'touchdeck': 'touchdeck.svg', 'animated-timer': 'animated-timer.svg'}


def static_svg(text):
    if not isinstance(text, str) or not text or len(text.encode()) > 65536:
        return False
    if re.search(r'<!DOCTYPE|<!ENTITY|@import', text, re.I):
        return False
    try:
        tree = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return False
    if tree.tag.split('}')[-1] != 'svg':
        return False
    for node in tree.iter():
        if node.tag.split('}')[-1].lower() in {'script', 'foreignobject', 'image', 'animate', 'animatetransform', 'animatemotion', 'set'}:
            return False
        for key, value in node.attrib.items():
            key = key.split('}')[-1].lower()
            if key.startswith('on') or (key == 'href' and not value.startswith('#')):
                return False
    return not any(not ref.strip(' \"\'').startswith('#') for ref in re.findall(r'url\(\s*([^)]*)\)', text, re.I))


def fallback_svg(manifest):
    ident = str(manifest.get('id', 'component'))
    if ident in BUILTIN:
        return (ASSETS / BUILTIN[ident]).read_text()
    digest = hashlib.sha256(ident.encode()).digest()
    color = QColor.fromHsv(int.from_bytes(digest[:2], 'big') % 360, 95, 170).name()
    words = re.findall(r'[^\W_]+', str(manifest.get('name') or ident), re.UNICODE)
    letters = ''.join(w[0] for w in words[:2]).upper() or '?'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
            '<rect x="4" y="4" width="120" height="120" rx="28" fill="#191c23"/>'
            f'<rect x="18" y="18" width="92" height="92" rx="23" fill="{color}"/>'
            f'<text x="64" y="66" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="sans-serif" font-size="40" font-weight="600" fill="#ffffff">{escape(letters)}</text></svg>')


class ComponentIcons:
    def __init__(self):
        self.cache = OrderedDict()

    def pixmap(self, manifest, svg='', size=80, ratio=1):
        if not isinstance(svg, str): svg = ""
        ratio = max(1, min(4, ratio))
        key = (manifest.get('id'), manifest.get('name'), hashlib.sha256(svg.encode()).digest(), size, ratio)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        renderer = QSvgRenderer(QByteArray(svg.encode())) if static_svg(svg) else None
        if renderer is None or not renderer.isValid() or renderer.animated():
            renderer = QSvgRenderer(QByteArray(fallback_svg(manifest).encode()))
        image = QPixmap(round(size * ratio), round(size * ratio)); image.fill(Qt.transparent)
        painter = QPainter(image); renderer.render(painter); painter.end()
        image.setDevicePixelRatio(ratio)
        self.cache[key] = image
        if len(self.cache) > 128:
            self.cache.popitem(last=False)
        return image

    def icon(self, manifest, svg='', size=48, ratio=1):
        image = self.pixmap(manifest, svg, size, ratio)
        icon = QIcon()
        for mode in (QIcon.Normal, QIcon.Active, QIcon.Selected):
            for state in (QIcon.Off, QIcon.On):
                icon.addPixmap(image, mode, state)
        return icon
