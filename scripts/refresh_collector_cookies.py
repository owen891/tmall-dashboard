"""Refresh the collector cookie cache files from the live browser session.

Why this exists (2026-10-22 incident): ``cookie_store.get_cookie_header`` uses the
saved file whenever it is younger than ``PLATFORM_MAX_AGE`` (7 days for Taobao
properties) and only falls back to CDP once it is older. Taobao rotates the
session cookies well inside that window, so a 4-day-old file kept being replayed
and every sycm call failed with "You must login system first" while the browser
itself was still logged in.

Refreshing the file on every boot closes that gap without touching the collector
code path: the file is re-derived from the same profile the collectors drive.

BI is skipped on purpose: ``cookie_store._fetch_from_cdp('bi')`` raises
``EXPLICIT_SESSION_REFRESH_REQUIRED``; that session is refreshed only by an
explicit, human-authorized login.

Usage:
    python scripts/refresh_collector_cookies.py [--platforms sycm,wanxiangtai] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

COLLECTORS_DIR = os.environ.get(
    'TMALL_COLLECTORS_DIR',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'collectors'))
DEFAULT_PLATFORMS = ('sycm', 'wanxiangtai')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Refresh collector cookie cache files from CDP")
    parser.add_argument('--platforms', default=','.join(DEFAULT_PLATFORMS))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    if COLLECTORS_DIR not in sys.path:
        sys.path.insert(0, COLLECTORS_DIR)
    try:
        import cookie_store  # noqa: PLC0415 - runtime dependency, resolved lazily
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({'ok': False, 'code': 'COOKIE_STORE_IMPORT_FAILED', 'error': str(exc)}))
        return 21

    results = {}
    failed = 0
    for platform in [p.strip() for p in args.platforms.split(',') if p.strip()]:
        try:
            cookies = cookie_store._fetch_from_cdp(platform)  # noqa: SLF001 - intended entry point
            if not cookies:
                results[platform] = {'ok': False, 'code': 'EMPTY_COOKIES'}
                failed += 1
                continue
            cookie_store.save_cookie_file(platform, cookies)
            results[platform] = {'ok': True, 'count': len(cookies)}
        except Exception as exc:  # noqa: BLE001 - one platform must not abort the rest
            results[platform] = {'ok': False, 'code': 'REFRESH_FAILED', 'error': str(exc)[:200]}
            failed += 1

    payload = {'ok': failed == 0, 'platforms': results}
    print(json.dumps(payload, ensure_ascii=not args.json))
    return 0 if failed == 0 else 22


if __name__ == '__main__':
    sys.exit(main())
