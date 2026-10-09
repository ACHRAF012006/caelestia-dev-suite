"""Shared component artwork and complete, push-required task context."""
import json

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from app.component_icons import ComponentIcons, static_svg
from app.main import Window
from backend.codex import context
from backend.store import DEFAULT_REPOSITORY, source_hash


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_declared_icon_matches_in_components_and_store(qt_app, manager, app_files):
    manifest, files = app_files
    manifest['desktop'] = {'icon': 'assets/identity.svg'}
    files['assets/identity.svg'] = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect width="128" height="128" fill="#85b79e"/></svg>'
    files['manifest.json'] = json.dumps(manifest)
    manager.create(files)
    view = Window(manager)
    try:
        row = view.components.item(0)
        assert not row.icon().isNull()
        assert view.component_name.text() == manifest['name']
        assert view.component_icon.pixmap().toImage().pixelColor(25, 25).name() == '#85b79e'
        entry = {'manifest': manifest, 'files': files, 'hash': source_hash(files)}
        store_image = view.store_page.app_image(entry).toImage()
        assert store_image.pixelColor(25, 25).name() == '#85b79e'
        # Opening pages reuses the snapshot and identity, without rereading files.
        def unavailable(*_): raise AssertionError('Navigation reread component source')
        manager.read_source = unavailable
        view.navigate('Components'); view.navigate('Codex Context')
        assert 'REQUIRED GIT DELIVERY' in view.context_editor.toPlainText()
    finally:
        view.close(); qt_app.processEvents()


def test_component_fallbacks_are_distinct_stable_and_support_scaling(qt_app):
    renderer = ComponentIcons()
    images = [renderer.pixmap({'id': ident, 'name': ident}).toImage() for ident in ('cast-audio', 'touchdeck', 'animated-timer', 'new-notes', 'other-notes')]
    assert all(not image.isNull() for image in images)
    assert all(a != b for i, a in enumerate(images) for b in images[i + 1:])
    renderer.cache.clear()
    assert renderer.pixmap({'id': 'cast-audio', 'name': 'cast-audio'}).toImage() == images[0]
    large = renderer.pixmap({'id': 'animated-timer'}, size=48, ratio=2)
    assert large.width() == 96 and large.devicePixelRatio() == 2
    icon = renderer.icon({'id': 'animated-timer'})
    assert icon.pixmap(48, 48, QIcon.Selected).toImage() == icon.pixmap(48, 48, QIcon.Normal).toImage()


@pytest.mark.parametrize('content', [
    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://example.com/icon.svg"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><style>@import "https://example.com/style";</style></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(file:///tmp/icon)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><animate attributeName="x"/></svg>',
])
def test_untrusted_active_or_external_svg_uses_identity_fallback(qt_app, content):
    assert not static_svg(content)
    icons = ComponentIcons(); manifest = {'id': 'animated-timer', 'name': 'Timer'}
    assert icons.pixmap(manifest, content).toImage() == icons.pixmap(manifest).toImage()


def test_context_requires_verified_scoped_push_and_current_adapters(manager, app_files):
    _, files = app_files; manager.create(files)
    statuses = manager.all_status()
    manager.all_status = lambda: pytest.fail('Context ignored its inspection snapshot')
    prompt = context(manager, 'Improve the timer interface', statuses=statuses)
    assert prompt.index('CURRENT REQUEST:') < prompt.index('Existing components:')
    assert 'Improve the timer interface' in prompt
    for expected in ('Always commit and push', 'Stage explicit task-owned paths or hunks',
                     'fresh Git read', 'never claim that they were pushed',
                     'caelestia-dashboard-timer', 'caelestia-quick-toggles',
                     'docs/ANIMATED_TIMER_INTEGRATION.md', 'assets/icon.svg',
                     'CAELESTIA_DEV_PACKAGE', 'temporary XDG', DEFAULT_REPOSITORY):
        assert expected in prompt
    assert 'When the current request authorizes GitHub publishing' not in prompt
