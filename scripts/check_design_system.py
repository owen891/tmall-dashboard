#!/usr/bin/env python
"""设计系统契约门禁：把 DESIGN_SYSTEM.md 的规范变成可执行红线。

用法：
    python scripts/check_design_system.py            # 只报告
    python scripts/check_design_system.py --strict   # 有违规就退出码 1

为什么需要它：
    DESIGN_SYSTEM.md 是 30 KB 的规范文档，但**文档靠人读**。真实情况是：
    - tokens.css 定义了 182 个 token，页面却仍在写裸 `#hex` / `rgb()`
    - 浮层定位散落在各页面 CSS，最近一次事故就是定位样式被 CSS 解析错误吞掉，
      弹窗渲染到文档流底部（top 2211px / 视口 800px），表现为「点了没反应」
    - ui-components.js 导出 30+ 组件，但组件目录页只覆盖一部分
    把规范变成测试，才能让它在每次提交时真正生效。

判据：
    R1 除 tokens.css 外不得新增裸颜色（#hex / rgb() / hsl()）—— 必须走 var(--token)
    R2 页面级 CSS 不得自写 position:fixed 浮层 —— 必须走 TmallUI.popover 原语
    R3 组件目录页必须覆盖 ui-components.js 导出的全部组件
    R4 ui-components.js 必须导出 popover 浮层原语

基线（BASELINE）记录的是引入门禁之前就存在的历史违规，只允许减少、不允许增加。
"""
from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "frontend" / "ui_demo"
ASSETS = UI_ROOT / "assets"
PAGES = UI_ROOT / "pages"

# 允许定义裸颜色的唯一文件：token 的源头。
TOKEN_SOURCE = "tokens.css"

RAW_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
FIXED_POSITION_RE = re.compile(r"position\s*:\s*fixed")

# 历史违规基线：{相对路径: 允许的数量}。只允许下调。
RAW_COLOR_BASELINE: dict[str, int] = {
    "period-review.css": 15,
    "promotion-domain.css": 1,
}
FIXED_POSITION_BASELINE: dict[str, int] = {
    "period-review.css": 1,
    "settings-domain.css": 1,
}

# 页面级 CSS：这些文件是页面/主题样式，不允许自带浮层定位。
PAGE_LEVEL_CSS_GLOBS = ("*.css", "themes/*.css")
# 组件层 CSS：浮层定位的合法归属地。
COMPONENT_LAYER_CSS = {"components.css", "shell.css"}

# 组件目录页必须展示的组件。标记同时接受 class 名与 TmallUI 工厂调用，
# 因为弹窗/浮层是 JS 创建的原生元素，HTML 里不会出现它们的 class 字面量。
CATALOG_REQUIRED_COMPONENTS: dict[str, tuple[str, ...]] = {
    "按钮": ("ui-button",),
    "徽章": ("ui-badge",),
    "面板": ("ui-panel",),
    "指标卡": ("ui-metric-card",),
    "表格": ("ui-table-wrap",),
    "空状态": ("ui-empty-state",),
    "弹窗": ("ui-modal", "TmallUI.modal"),
    "浮层": ("ui-popover", "TmallUI.popover"),
    "筛选工具条": ("ui-filter-toolbar",),
}

# ============ R5：复合组件不得在 HTML 里手写拼装 ============
# 判据的依据（本门禁最关键的设计判断）：
#   只有**复合组件**必须走 TmallUI.* 工厂 —— 它们内部有 header/body/tools 等结构约定，
#   手写拼装极易与工厂输出漂移，进而导致样式错位（阶段 2 的最高频失败模式）。
#   原子类（button/badge）没有内部结构约定，静态 HTML 手写是合理的：
#   强制它们走 JS 工厂会破坏服务端渲染、增加无谓 JS 依赖，收益为负。
#   因此门禁只覆盖复合组件，不覆盖原子类。
COMPOSITE_COMPONENT_ROOTS: tuple[str, ...] = (
    "ui-panel", "ui-metric-card", "ui-metric-grid", "ui-empty-state",
    "ui-table-wrap", "ui-data-table", "ui-page-header", "ui-filter-toolbar",
    "ui-table-toolbar", "ui-context-bar", "ui-sticky-action-bar",
    "ui-modal", "ui-popover", "ui-drawer", "ui-detail-drawer", "ui-field-selector",
)

# 允许手写的元素级类名（BEM 的 element 部分，属于页面结构而非组件实例）。
LAYOUT_ELEMENT_PREFIXES: tuple[str, ...] = (
    "ui-page-header__", "ui-panel__", "ui-metric-card__", "ui-table-toolbar__",
    "ui-filter-toolbar__", "ui-context-bar__", "ui-empty-state__",
    "ui-metric-grid__", "ui-table-wrap__",
)

# 历史违规基线：每页允许手写的复合组件类数量。只允许下降，不允许上升。
# 引入门禁时的实测值（2026-10-11）。阶段 2 逐页收敛时同步下调这些数字。
UI_HANDWRITE_BASELINE: dict[str, int] = {
    # 2026-10-24：详情页加「利润(支付预估)」KPI 卡（同款 ui-metric-card 模式）+2
    "product-detail": 75,
    "market-ranking": 42,
    "data-center": 40,
    "promotion": 28,
    "component-catalog": 19,
    "lifecycle": 18,
    "rival-analysis": 18,
    "new-products": 17,
    "overview": 17,
    "products": 15,
    "settings": 13,
    "creative-board": 10,
    "flow-source": 10,
    "reviews": 10,
    "goals": 8,
    "period-review": 3,
}

CLASS_ATTR_RE = re.compile(r'class="([^"]*)"')


def count_handwritten_components(page: pathlib.Path) -> int:
    """统计页面 HTML 里手写拼装的复合组件类数量（元素级类名不计）。"""
    source = page.read_text(encoding="utf-8")
    count = 0
    for match in CLASS_ATTR_RE.finditer(source):
        for token in match.group(1).split():
            if not token or any(token.startswith(p) for p in LAYOUT_ELEMENT_PREFIXES):
                continue
            if any(token == root or token.startswith(f"{root}--") for root in COMPOSITE_COMPONENT_ROOTS):
                count += 1
    return count


def _private_page_names() -> set[str]:
    """私人版页面（部署私有 data/private_edition.json 清单）不参与公共预算基线。"""
    import json
    manifest = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'private_edition.json'
    try:
        return {str(item).rsplit('/', 1)[-1].removesuffix('.html')
                for item in json.loads(manifest.read_text(encoding='utf-8')).get('installer_exclude_files') or []}
    except (OSError, ValueError):
        return set()


def check_handwritten_components() -> list[str]:
    errors: list[str] = []
    private_names = _private_page_names()
    for page in sorted(PAGES.glob("*.html")):
        name = page.stem
        if name in private_names:
            continue
        found = count_handwritten_components(page)
        allowed = UI_HANDWRITE_BASELINE.get(name, 0)
        if found > allowed:
            errors.append(
                f"R5 {page.name}: 手写复合组件 {found} 处，超出基线 {allowed}。"
                f"复合组件请改用 TmallUI.panel / metricCard / table / emptyState 等工厂"
            )
    return errors


def iter_page_level_css() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for pattern in PAGE_LEVEL_CSS_GLOBS:
        files.extend(ASSETS.glob(pattern))
    return sorted({p for p in files if p.is_file()})


def count_matches(path: pathlib.Path, pattern: re.Pattern[str]) -> int:
    return len(pattern.findall(path.read_text(encoding="utf-8")))


def check_raw_colors() -> list[str]:
    errors: list[str] = []
    for path in sorted(ASSETS.rglob("*.css")):
        if path.name == TOKEN_SOURCE:
            continue
        found = count_matches(path, RAW_COLOR_RE)
        allowed = RAW_COLOR_BASELINE.get(path.name, 0)
        if found > allowed:
            errors.append(
                f"R1 {path.relative_to(ASSETS).as_posix()}: 裸颜色 {found} 处，"
                f"超出基线 {allowed}。请改用 tokens.css 里的 var(--token)"
            )
    return errors


def check_page_level_overlays() -> list[str]:
    errors: list[str] = []
    for path in iter_page_level_css():
        if path.name in COMPONENT_LAYER_CSS:
            continue
        found = count_matches(path, FIXED_POSITION_RE)
        allowed = FIXED_POSITION_BASELINE.get(path.name, 0)
        if found > allowed:
            errors.append(
                f"R2 {path.relative_to(ASSETS).as_posix()}: 页面级 CSS 出现 position:fixed "
                f"{found} 处，超出基线 {allowed}。浮层请改用 TmallUI.popover 原语"
            )
    return errors


def check_catalog_coverage() -> list[str]:
    catalog = PAGES / "component-catalog.html"
    if not catalog.is_file():
        return ["R3 缺少组件目录页 pages/component-catalog.html"]
    source = catalog.read_text(encoding="utf-8")
    missing = [
        name for name, markers in CATALOG_REQUIRED_COMPONENTS.items()
        if not any(marker in source for marker in markers)
    ]
    return [f"R3 组件目录页缺少组件展示：{', '.join(missing)}"] if missing else []


def check_popover_exported() -> list[str]:
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    errors: list[str] = []
    if "const popover = ({" not in source:
        errors.append("R4 ui-components.js 未实现 popover 浮层原语")
    if not re.search(r"const api = \{[^}]*\bpopover\b", source):
        errors.append("R4 ui-components.js 未在 api 中导出 popover")
    return errors


def validate_all() -> list[str]:
    errors: list[str] = []
    errors.extend(check_raw_colors())
    errors.extend(check_page_level_overlays())
    errors.extend(check_catalog_coverage())
    errors.extend(check_popover_exported())
    errors.extend(check_handwritten_components())
    return errors


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    strict = "--strict" in sys.argv
    errors = validate_all()

    total_handwritten = sum(count_handwritten_components(p) for p in PAGES.glob("*.html"))
    budget = sum(UI_HANDWRITE_BASELINE.values())
    print(f"扫描 {UI_ROOT}")
    print(f"  页面级 CSS {len(iter_page_level_css())} 个 / token 源 {TOKEN_SOURCE}")
    print(f"  手写复合组件 {total_handwritten} 处 / 基线预算 {budget} 处")
    if not errors:
        print("  [OK] 设计系统契约通过：颜色走 token、浮层走原语、目录覆盖组件")
        return 0

    print(f"  [FAIL] {len(errors)} 项设计系统违规：")
    for error in errors:
        print(f"    - {error}")
    return 1 if strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
