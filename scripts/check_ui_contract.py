"""Validate the static HTML/CSS/JS contract for the native UI component system."""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "frontend" / "ui_demo" / "pages"
ASSETS = ROOT / "frontend" / "ui_demo" / "assets"

LEGACY_ROOTS = {
    "button", "button--primary", "button--ghost", "button--danger", "button--icon", "button--sm",
    "badge", "badge--brand", "badge--success", "badge--warning", "badge--danger", "badge--info", "badge--purple", "badge--muted",
    "panel", "plain-panel", "metric-card", "metric-card--drillable", "data-table-wrap", "data-table-wrap--discoverable",
    "data-table-wrap--scroll", "data-table", "empty-state", "section-toolbar", "demo-page__intro", "metric-grid",
}
LEGACY_CLASS_RE = re.compile(r"(?<![\w-])(?:" + "|".join(sorted(map(re.escape, LEGACY_ROOTS), key=len, reverse=True)) + r")(?![\w-])")
CSS_LEGACY_SELECTOR_RE = re.compile(r"(?<![\w-])\.(?:" + "|".join(sorted(map(re.escape, LEGACY_ROOTS), key=len, reverse=True)) + r")(?![\w-])")
CLASS_LITERAL_RE = re.compile(r"(?:className\s*[:=]|class\s*=|(?:element|create|node)\(\s*['\"][^'\"]+['\"]\s*,\s*)\s*['\"`]([^'\"`]*)['\"`]")
TEMPLATE_CLASS_RE = re.compile(r"class\s*=\s*['\"]([^'\"]*)['\"]")


def legacy_tokens(value: str) -> list[str]:
    return sorted(set(match.group(0) for match in LEGACY_CLASS_RE.finditer(value)))


def validate_page(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for required in ("../assets/tokens.css", "../assets/components.css", "data-shell-sidebar", "data-shell-header"):
        if required not in source:
            errors.append(f"missing {required}")
    for raw in re.findall(r'class=["\']([^"\']+)["\']', source):
        errors.extend(f"legacy class in HTML: {token}" for token in legacy_tokens(raw))
    return sorted(set(errors))


def validate_styles() -> list[str]:
    errors: list[str] = []
    for path in sorted(ASSETS.glob("*.css")):
        source = path.read_text(encoding="utf-8")
        for match in CSS_LEGACY_SELECTOR_RE.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            errors.append(f"{path.name}:{line}: legacy CSS selector .{match.group(0)[1:]}")
    return errors


def validate_scripts() -> list[str]:
    errors: list[str] = []
    for path in sorted(ASSETS.glob("*.js")):
        if path.name.endswith(".min.js") or path.name == "ui-components.js":
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in (CLASS_LITERAL_RE, TEMPLATE_CLASS_RE):
            for match in pattern.finditer(source):
                for token in legacy_tokens(match.group(1)):
                    line = source.count("\n", 0, match.start()) + 1
                    errors.append(f"{path.name}:{line}: legacy JS class literal {token}")
    return sorted(set(errors))


def validate_title_contract() -> list[str]:
    errors: list[str] = []
    tokens = (ASSETS / "tokens.css").read_text(encoding="utf-8")
    for token in ("--title-width-sm", "--title-width-md", "--title-width-lg", "--title-width-page"):
        if token not in tokens:
            errors.append(f"missing title token {token}")
    components = (ASSETS / "components.css").read_text(encoding="utf-8")
    for required in ("text-overflow: ellipsis", "white-space: nowrap", ".ui-panel__title", ".ui-metric-card__label"):
        if required not in components:
            errors.append(f"missing title rule {required}")
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
    errors = validate_styles() + validate_scripts() + validate_title_contract()
    if errors:
        failures += 1
        print("FAIL shared assets:")
        print("\n".join(f"  {error}" for error in errors))
    else:
        print("OK   shared assets")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
