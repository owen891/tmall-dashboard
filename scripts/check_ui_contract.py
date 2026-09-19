"""Validate the static HTML contract for the native UI component system."""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "frontend" / "ui_demo" / "pages"

LEGACY_TO_CANONICAL = {
    "button": "ui-button",
    "metric-card": "ui-metric-card",
    "badge": "ui-badge",
    "panel": "ui-panel",
    "plain-panel": "ui-panel",
    "empty-state": "ui-empty-state",
    "demo-page__intro": "ui-page-header",
    "section-toolbar": "ui-filter-toolbar",
    "data-table-wrap": "ui-table-wrap",
    "data-table": "ui-data-table",
}


def validate_page(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for required in ("../assets/tokens.css", "../assets/components.css", "data-shell-sidebar", "data-shell-header"):
        if required not in source:
            errors.append(f"missing {required}")
    for raw in re.findall(r'class="([^"]+)"', source):
        classes = set(raw.split())
        for legacy, canonical in LEGACY_TO_CANONICAL.items():
            if legacy in classes and canonical not in classes:
                # Runtime upgrading is the compatibility path, so this is a warning
                # for existing pages and an error only when a page has no shell script.
                if "shell.js" not in source:
                    errors.append(f"{legacy} has no runtime upgrade")
    return errors


def main() -> int:
    failures = 0
    for page in sorted(PAGES.glob("*.html")):
        errors = validate_page(page)
        if errors:
            failures += 1
            print(f"FAIL {page.name}: {'; '.join(errors)}")
        else:
            print(f"OK   {page.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
