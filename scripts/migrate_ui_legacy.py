"""One-shot codemod: migrate legacy root UI classes to the canonical ui-* namespace.

Scope (phase 1 of the dual-track collapse):
- Roots, variants and wrappers: button, badge (+--tones), panel, plain-panel,
  metric-card (+--drillable), data-table, data-table-wrap (+--discoverable/--scroll),
  empty-state, section-toolbar, demo-page__intro, metric-grid.
- Child element classes (panel__title, metric-card__label, ...) are intentionally
  kept: their legacy CSS rules stay authoritative until the page-family migration
  renames them together with the CSS.

HTML: only class="..."/class='...' attribute values are rewritten.
JS: only class-list string literals in class contexts (className=, classList.*,
second argument of create()/node() helpers, class="" fragments inside template
literals, "."-prefixed selectors, and the 'button--'/'badge--' prefix literals).
createElement('button') tag names and type="button" attributes are never touched.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "frontend" / "ui_demo" / "pages"
ASSETS = ROOT / "frontend" / "ui_demo" / "assets"

TOKEN_MAP = {
    "button": "ui-button",
    "badge": "ui-badge",
    "panel": "ui-panel",
    "plain-panel": "ui-panel",
    "metric-card": "ui-metric-card",
    "data-table": "ui-data-table",
    "data-table-wrap": "ui-table-wrap",
    "empty-state": "ui-empty-state",
    "section-toolbar": "ui-filter-toolbar",
    "demo-page__intro": "ui-page-header",
    "metric-grid": "ui-metric-grid",
}
for _tone in ("brand", "success", "warning", "danger", "info", "purple", "muted", "secondary"):
    TOKEN_MAP[f"badge--{_tone}"] = f"ui-badge--{_tone}"
for _variant in ("primary", "ghost", "danger", "icon", "sm"):
    TOKEN_MAP[f"button--{_variant}"] = f"ui-button--{_variant}"
TOKEN_MAP["metric-card--drillable"] = "ui-metric-card--drillable"
TOKEN_MAP["data-table-wrap--discoverable"] = "ui-table-wrap--discoverable"
TOKEN_MAP["data-table-wrap--scroll"] = "ui-table-wrap--scroll"

TOKEN_RE = re.compile(r"(?<![\w-])(" + "|".join(sorted(TOKEN_MAP, key=len, reverse=True)) + r")(?![\w-])")


def map_class_list(value: str) -> str:
    seen: list[str] = []
    for token in TOKEN_RE.sub(lambda m: TOKEN_MAP[m.group(1)], value).split():
        if token not in seen:
            seen.append(token)
    return " ".join(seen)


def migrate_html(source: str) -> tuple[str, int]:
    count = 0

    def repl_double(m: re.Match) -> str:
        nonlocal count
        mapped = map_class_list(m.group(1))
        if mapped != m.group(1):
            count += 1
        return f'class="{mapped}"'

    def repl_single(m: re.Match) -> str:
        nonlocal count
        mapped = map_class_list(m.group(1))
        if mapped != m.group(1):
            count += 1
        return f"class='{mapped}'"

    source = re.sub(r'class="([^"]*)"', repl_double, source)
    source = re.sub(r"class='([^']*)'", repl_single, source)
    return source, count


# class-list contexts in JS: className assignments, classList calls, and the
# second argument of the create()/node() DOM helper used across live scripts.
CLASS_CONTEXTS = [
    re.compile(r"(className\s*[:=]\s*)(['\"])([^'\"]*)\2"),
    re.compile(r"(classList\.(?:add|toggle|remove|replace)\(\s*)(['\"])([^'\"]*)\2"),
    re.compile(r"((?:create|node)\(\s*['\"][a-zA-Z]+['\"]\s*,\s*)(['\"])([^'\"]*)\2"),
    re.compile(r"(class=)(['\"])([^'\"]*)\2"),
]


def map_string_body(body: str) -> str:
    return map_class_list(body)


def migrate_js(source: str) -> tuple[str, int]:
    count = 0

    def ctx_repl(m: re.Match) -> str:
        nonlocal count
        mapped = map_string_body(m.group(3))
        if mapped != m.group(3):
            count += 1
        return f"{m.group(1)}{m.group(2)}{mapped}{m.group(2)}"

    for pattern in CLASS_CONTEXTS:
        source = pattern.sub(ctx_repl, source)

    # dotted selectors inside JS strings: '.button', '.panel .button--ghost', ...
    def dot_repl(m: re.Match) -> str:
        nonlocal count
        return f".{TOKEN_MAP[m.group(1)]}"

    dotted = re.compile(r"\.(" + "|".join(sorted(TOKEN_MAP, key=len, reverse=True)) + r")(?![\w-])")
    before = source
    source = dotted.sub(dot_repl, source)
    count += len(dotted.findall(before))

    # prefix literals used to build dynamic variant classes: 'badge--' + tone
    for prefix, canonical in (("badge--", "ui-badge--"), ("button--", "ui-button--")):
        standalone = re.compile(r"(['\"])(" + prefix + r")\1")
        source, n = standalone.subn(lambda m: m.group(1) + canonical + m.group(1), source)
        count += n
        # template fragments like badge--${tone}
        source, n = re.subn(prefix + r"(\$\{)", canonical + r"\1", source)
        count += n
    return source, count


def main() -> int:
    total = 0
    for page in sorted(PAGES.glob("*.html")):
        src = page.read_text(encoding="utf-8")
        out, n = migrate_html(src)
        if n:
            page.write_text(out, encoding="utf-8", newline="\n")
        total += n
        print(f"{page.name}: {n} class attribute(s)")
    for js in sorted(ASSETS.glob("*.js")):
        if js.name.endswith(".min.js") or js.name == "ui-components.js":
            continue
        src = js.read_text(encoding="utf-8")
        out, n = migrate_js(src)
        if n:
            js.write_text(out, encoding="utf-8", newline="\n")
        total += n
        if n:
            print(f"{js.name}: {n} string literal(s)")
    print(f"TOTAL: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
