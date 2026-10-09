"""Shared dashboard ownership and recoverable, sealed membership transactions.

One receipt coordinates every dashboard-page component. Legacy Timer receipts
remain untouched until composition is needed and are reconstructed when the last
page leaves. The coordinator journals both receipts alongside the two host files.
"""
import json
from backend.paths import SafetyError, atomic_write, digest, no_symlinks, component_id
from backend.dashboard_contract import requested, declaration
from backend import dashboard_compat as compat, timer_integration as timer

ID = 'dashboard-pages'
FILES = compat.FILES


def receipt_path(paths):
    return no_symlinks(paths.manager / 'host-integrations/dashboard-pages.json')


def raw_at(path):
    if not path.exists(): return None
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise SafetyError('Missing or oversized dashboard receipt')
    return path.read_text(encoding='utf-8')


def make_receipt(paths, originals, modes, pages, with_timer):
    return {'id': ID, 'adapter_version': 1, 'originals': originals, 'modes': modes,
            'pages': pages, 'timer': with_timer,
            'checksums': {n: digest(v.encode()) for n, v in compat.sources(originals, pages, with_timer, paths).items()}}


def validate_receipt(paths, receipt):
    try:
        if set(receipt) != {'id', 'adapter_version', 'originals', 'modes', 'pages', 'timer', 'checksums'} or receipt['id'] != ID or receipt['adapter_version'] != 1 or type(receipt['timer']) is not bool:
            raise ValueError()
        for key in ('originals', 'modes', 'checksums'):
            if set(receipt[key]) != set(FILES): raise ValueError()
        for name in FILES:
            if digest(receipt['originals'][name].encode()) != FILES[name] or type(receipt['modes'][name]) is not int or not 0 <= receipt['modes'][name] <= 0o777:
                raise ValueError()
        if not isinstance(receipt['pages'], dict) or not 1 <= len(receipt['pages']) <= 128: raise ValueError()
        seen = set()
        for owner, page in receipt['pages'].items():
            component_id(owner)
            declaration(page)
            if page['id'] in seen: raise ValueError()
            seen.add(page['id'])
        if receipt != make_receipt(paths, receipt['originals'], receipt['modes'], receipt['pages'], receipt['timer']): raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise SafetyError('Invalid shared dashboard receipt') from error
    return receipt


def read_receipt(paths):
    raw = raw_at(receipt_path(paths))
    if raw is None: return None, None
    try: receipt = json.loads(raw)
    except ValueError as error: raise SafetyError('Invalid shared dashboard receipt') from error
    return validate_receipt(paths, receipt), raw


def participates(paths, manifest):
    if requested(manifest): return True
    receipt, _ = read_receipt(paths)
    return bool(receipt and (manifest.get('id') in receipt['pages'] or manifest.get('id') == 'animated-timer'))


def verify_release(paths):
    try:
        valid = no_symlinks(paths.shell / '.current_commit').read_text().strip() == compat.COMMIT and no_symlinks(paths.shell / '.current_version').read_text().strip().removeprefix('VERSION=').lstrip('v') == compat.VERSION
    except OSError as error:
        raise SafetyError('Dashboard requires verified Caelestia KDE v2.5.1 release markers') from error
    if not valid: raise SafetyError('Dashboard requires verified Caelestia KDE v2.5.1 at ' + compat.COMMIT)


def legacy_receipt(originals, modes, with_timer):
    return {'id': 'animated-timer', 'adapter_version': 1, 'originals': originals,
            'checksums': {n: digest(v.encode()) for n, v in timer.panel_sources(originals).items()}, 'modes': modes} if with_timer else None


def plan(paths, manifest):
    receipt, raw = read_receipt(paths)
    legacy, legacy_raw = timer.read_receipt(paths)
    if not requested(manifest) and not (receipt and (manifest['id'] in receipt['pages'] or manifest['id'] == 'animated-timer')):
        return None
    verify_release(paths)
    if receipt and bool(legacy) != receipt['timer']:
        raise SafetyError('Dashboard and Timer receipts disagree')
    baseline = receipt or legacy
    originals, before, modes = {}, {}, {}
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if not path.is_file() or path.stat().st_size > 512 * 1024: raise SafetyError('Missing or oversized dashboard host file: ' + name)
        value, mode = path.read_text(), path.stat().st_mode & 0o777
        expected = baseline['checksums'][name] if baseline else FILES[name]
        if digest(value.encode()) != expected or (baseline and mode != baseline['modes'][name]):
            raise SafetyError('Dashboard host file changed; preserve/reconcile edits: ' + name)
        originals[name] = baseline['originals'][name] if baseline else value
        before[name], modes[name] = value, mode
    pages = dict(receipt['pages']) if receipt else {}
    with_timer = receipt['timer'] if receipt else bool(legacy)
    owner = manifest['id']
    pages.pop(owner, None)
    if requested(manifest): pages[owner] = declaration(manifest['integration']['dashboard'])
    elif owner == 'animated-timer': with_timer = timer.requested(manifest)
    if len(pages) > 128 or len({p['id'] for p in pages.values()}) != len(pages):
        raise SafetyError('Duplicate dashboard page ID or too many dashboard pages')
    after = compat.sources(originals, pages, with_timer, paths)
    updated = make_receipt(paths, originals, modes, pages, with_timer) if pages else None
    return {'id': ID, 'before': before, 'after': after, 'modes': modes,
            'receipt_before': raw, 'receipt_after': updated, 'legacy_before': legacy_raw,
            'legacy_after': legacy_receipt(originals, modes, with_timer),
            'pages': pages, 'timer': with_timer, 'originals': originals,
            'summary': 'Reconcile shared dashboard pages, preserve other registrations, enable the plugin and restart the Caelestia KDE shell.'}


def validate_plan(paths, proposal):
    try:
        if proposal['id'] != ID or any(set(proposal[k]) != set(FILES) for k in ('before', 'after', 'modes', 'originals')): raise ValueError()
        pages, with_timer = proposal['pages'], proposal['timer']
        expected = make_receipt(paths, proposal['originals'], proposal['modes'], pages, with_timer)
        # Removal plans still validate pristine source and mode constraints.
        if pages: validate_receipt(paths, expected)
        else:
            for n in FILES:
                if digest(proposal['originals'][n].encode()) != FILES[n] or type(proposal['modes'][n]) is not int or not 0 <= proposal['modes'][n] <= 0o777: raise ValueError()
            if type(with_timer) is not bool: raise ValueError()
        if proposal['after'] != compat.sources(proposal['originals'], pages, with_timer, paths) or proposal['receipt_after'] != (expected if pages else None) or proposal['legacy_after'] != legacy_receipt(proposal['originals'], proposal['modes'], with_timer): raise ValueError()
        # Derive BEFORE from its receipts too; recovery never trusts journal code.
        prior = json.loads(proposal['receipt_before']) if proposal['receipt_before'] else None
        old_timer = json.loads(proposal['legacy_before']) if proposal['legacy_before'] else None
        if prior:
            validate_receipt(paths, prior)
            if bool(old_timer) != prior['timer']: raise ValueError()
        if old_timer != legacy_receipt(proposal['originals'], proposal['modes'], bool(old_timer)): raise ValueError()
        if proposal['before'] != compat.sources(proposal['originals'], prior['pages'] if prior else {}, prior['timer'] if prior else bool(old_timer), paths): raise ValueError()
        if prior and (prior['originals'] != proposal['originals'] or prior['modes'] != proposal['modes']): raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise SafetyError('Invalid shared dashboard transaction plan') from error


def check(paths, proposal):
    if proposal is None: return
    verify_release(paths)
    validate_plan(paths, proposal)
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if path.read_text() != proposal['before'][name] or path.stat().st_mode & 0o777 != proposal['modes'][name]:
            raise SafetyError('Dashboard host changed since preview')
    if raw_at(receipt_path(paths)) != proposal['receipt_before'] or raw_at(timer.receipt_path(paths)) != proposal['legacy_before']:
        raise SafetyError('Dashboard ownership changed since preview')


def write_receipt(path, value):
    if value is None:
        if path.exists(): path.unlink()
    else: atomic_write(path, json.dumps(value, indent=2).encode(), 0o600)


def apply(paths, proposal):
    if proposal is None: return
    check(paths, proposal)
    for name in FILES: atomic_write(paths.shell / name, proposal['after'][name].encode(), proposal['modes'][name])
    write_receipt(timer.receipt_path(paths), proposal['legacy_after'])
    write_receipt(receipt_path(paths), proposal['receipt_after'])


def recover(paths, proposal):
    if proposal is None: return
    validate_plan(paths, proposal)
    for name in FILES:
        path = no_symlinks(paths.shell / name)
        if path.read_text() not in (proposal['before'][name], proposal['after'][name]) or path.stat().st_mode & 0o777 != proposal['modes'][name]:
            raise SafetyError('Dashboard changed during recovery; preserve edits and reconcile manually')
    for path, old, new in ((receipt_path(paths), proposal['receipt_before'], proposal['receipt_after']), (timer.receipt_path(paths), proposal['legacy_before'], proposal['legacy_after'])):
        if raw_at(path) not in (old, json.dumps(new, indent=2) if new else None): raise SafetyError('Dashboard receipt changed during recovery')
    for name in FILES: atomic_write(paths.shell / name, proposal['before'][name].encode(), proposal['modes'][name])
    for path, raw in ((receipt_path(paths), proposal['receipt_before']), (timer.receipt_path(paths), proposal['legacy_before'])):
        if raw is None: write_receipt(path, None)
        else: atomic_write(path, raw.encode(), 0o600)
