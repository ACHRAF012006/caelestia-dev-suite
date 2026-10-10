"""Small read-only CLI; no non-reviewed lifecycle mutation commands."""
import argparse
import json
import sys
from pathlib import Path
from backend.paths import Paths, VERSION, SafetyError

COMMANDS = {'status', 'doctor', 'list', 'validate', 'backup'}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not any(arg in COMMANDS for arg in argv):
        from app.main import main as gui_main
        return gui_main()
    parser = argparse.ArgumentParser(description='Read-only Caelestia Dev Manager diagnostics')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--sandbox', type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'doctor', 'list'): sub.add_parser(name)
    validate = sub.add_parser('validate'); validate.add_argument('component')
    backup = sub.add_parser('backup'); backup.add_argument('action', choices=['list'])
    args = parser.parse_args(argv)
    paths = Paths.sandbox(args.sandbox) if args.sandbox else Paths.default(args.project)
    from backend.diagnostics import inspect, reader
    try:
        if args.command in {'status', 'doctor'}:
            value = inspect(paths, real=not bool(args.sandbox), verify_backups=args.command == 'doctor')
        elif args.command == 'backup':
            from backend.backups import Backups
            value = Backups(paths).catalog()
        elif not paths.database.exists(): value = []
        else:
            manager = reader(paths, real=not bool(args.sandbox))
            try:
                value = manager.validation(args.component) if args.command == 'validate' else [
                    {'id': r['id'], 'installed_version': r.get('installed_version'), 'source_version': r['manifest']['version'], 'enabled': r.get('enabled', False)}
                    for r in manager.registry.all()]
            finally: manager.registry.db.close()
        print(json.dumps(value, indent=2, ensure_ascii=False))
        if isinstance(value, dict) and (value.get('valid') is False or any(c['status'] == 'Failed' for c in value.get('checks', []))): return 1
        return 0
    except (OSError, ValueError, KeyError) as error:
        from backend.dependencies import clean_output
        print(clean_output(str(error)), file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
