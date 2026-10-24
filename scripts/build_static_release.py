"""Build/publish immutable UI assets without importing the app or database.

Run only after staging all source changes. No historical releases are deleted.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.static_release import activate_release, build_release, publish_release


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'publish', 'activate'))
    parser.add_argument('version', nargs='?')
    parser.add_argument('--source', type=Path, default=ROOT / 'frontend/ui_demo')
    parser.add_argument('--store', type=Path, default=ROOT / 'data/frontend-releases')
    args = parser.parse_args(argv)
    if args.action == 'activate':
        if not args.version:
            parser.error('activate requires a retained version')
        version = activate_release(args.store, args.version)
    else:
        version = (build_release if args.action == 'build' else publish_release)(args.source, args.store)
    print(json.dumps({'action': args.action, 'version': version, 'store': str(args.store.resolve())}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
