"""Write the GitHub Release body from the CHANGELOG section for VERSION.

The release workflow used to let the release action generate notes, which
produced a bare "Full Changelog" link and dropped the hand-written update
notes. This extracts the matching section so the published release page
carries the same text as CHANGELOG.md.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def extract(version: str, changelog: str) -> str:
    start = changelog.find(f'## V{version}')
    if start < 0:
        raise SystemExit(f'CHANGELOG has no section for V{version}')
    rest = changelog[start:]
    # Next top-level version heading ends this section.
    following = re.search(r'\n## V\d', rest[3:])
    section = rest[:following.start() + 3] if following else rest
    lines = section.splitlines()
    if lines and lines[0].startswith('## '):
        lines = lines[1:]
    return '\n'.join(lines).strip() + '\n'


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    output = Path(argv[0]) if argv else PROJECT_ROOT / 'release-body.md'
    version = (PROJECT_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    changelog = (PROJECT_ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    body = extract(version, changelog)
    if len(body.strip()) < 80:
        raise SystemExit(f'Extracted release body looks empty for V{version}')
    output.write_text(body, encoding='utf-8')
    print(f'wrote {output} for V{version} ({len(body)} chars)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
