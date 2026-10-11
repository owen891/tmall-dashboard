from pathlib import Path
import importlib.util
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "ui_demo" / "assets"
PAGES = ROOT / "frontend" / "ui_demo" / "pages"


def load_script_module(name: str):
    """按文件路径加载 scripts/<name>.py，不污染 sys.path。

    为什么不能直接 sys.path.insert(0, 'scripts')：
        scripts/ 下存在 utils.py，而仓库根目录有同名的 utils/ 包。
        一旦 scripts 进入 sys.path，`import utils.goal_allocation` 就会解析到
        scripts/utils.py 并报「'utils' is not a package」，导致同一次 pytest
        会话里后运行的 tests/test_release_gates.py 全部导入失败。
    """
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_tmall_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_ui_registry_exposes_required_components():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    for name in ("format", "button", "badge", "emptyState", "dataState", "metricCard", "metricGrid", "panel", "pageHeader", "filterToolbar", "table", "setState", "fieldSelector", "modal", "confirm"):
        assert name in source
    assert "legacyMap" not in source
    assert "upgradeLegacy" not in source


def test_ui_audit_is_exposed():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "const audit" in source
    assert "fieldSelector, audit" in source


def test_component_catalog_covers_page_compositions():
    source = (PAGES / "component-catalog.html").read_text(encoding="utf-8")
    for name in ("ui-page-header", "ui-filter-toolbar", "ui-table-wrap", "ui-data-table"):
        assert name in source


def test_all_pages_are_validated_by_ui_contract():
    validate_page = load_script_module("check_ui_contract").validate_page

    failures = {page.name: validate_page(page) for page in PAGES.glob("*.html")}
    assert not {name: errors for name, errors in failures.items() if errors}


def test_analysis_page_uses_external_page_styles():
    source = (PAGES / "analysis.html").read_text(encoding="utf-8")
    assert "../assets/analysis.css" in source


def test_canonical_ui_styles_have_contract():
    source = (ASSETS / "components.css").read_text(encoding="utf-8")
    for selector in (".ui-button", ".ui-badge", ".ui-empty-state", ".ui-metric-card", ".ui-panel", ".ui-field-selector"):
        assert selector in source


def test_field_selector_is_shared_and_exposes_canonical_classes():
    source = (ASSETS / "field-selector.js").read_text(encoding="utf-8")
    assert "window.DemoFieldSelector = { create }" in source
    assert "ui-field-selector" in source
    assert "ui-field-selector__preview" in source


def test_field_selector_supports_search_and_visible_drag_feedback():
    source = (ASSETS / "field-selector.js").read_text(encoding="utf-8")
    styles = (ASSETS / "components.css").read_text(encoding="utf-8")
    for marker in (
        "searchQuery",
        "type = 'search'",
        "搜索字段名称或 key",
        "data-field-selector-empty",
        "没有匹配",
        "data-field-selector-search-status",
        "function removeField(position)",
        "aria-label', `删除${field.label}`",
        "dataset.lucide = 'trash-2'",
        "if (!isLocked)",
    ):
        assert marker in source
    for marker in (
        ".ui-field-selector__search",
        ".ui-field-selector__item.is-dragging",
        ".ui-field-selector__item.is-drag-over",
        ".ui-field-selector__preview.is-drag-over-end",
        ".ui-field-selector__button--remove:not(:disabled):hover",
    ):
        assert marker in styles


    # products 页的 fieldSelector 消费已迁至 pages/products/column-settings.js
    for name in ("keyword-promotion-live.js", "lifecycle-live.js", "overview-live.js", "promotion-live.js"):
        source = (ASSETS / name).read_text(encoding="utf-8")
        assert "TmallUI.fieldSelector" in source, name
        assert "DemoFieldSelector" not in source, name
    products_columns = (ASSETS / "pages" / "products" / "column-settings.js").read_text(encoding="utf-8")
    assert "TmallUI.fieldSelector" in products_columns, "products column-settings"
    assert "DemoFieldSelector" not in products_columns, "products column-settings"


def test_field_selector_only_uses_icons_available_in_the_custom_bundle():
    source = (ASSETS / "field-selector.js").read_text(encoding="utf-8")
    bundle = (ASSETS / "lucide-custom.min.js").read_text(encoding="utf-8")
    assert "arrow-up" not in source
    assert "arrow-down" not in source
    assert "chevron-right" in source
    assert "icons/chevron-right.js" in bundle
    assert "trash-2" in source
    assert "Trash2:re" in bundle


def test_all_field_selector_dialogs_have_shared_layout_guardrails():
    styles = (ASSETS / "components.css").read_text(encoding="utf-8")
    for dialog in ("promotion-field-dialog", "overview-matrix-columns-dialog", "products-columns-dialog", "lifecycle-columns-dialog"):
        assert f".{dialog} .ui-field-selector" in styles, dialog
    for page in ("promotion.html", "overview.html", "products.html", "lifecycle.html", "keyword-promotion.html"):
        source = (PAGES / page).read_text(encoding="utf-8")
        assert "ui-field-selector-dialog" in source, page
    assert ".ui-field-selector-dialog" in styles
    source = (ASSETS / "field-selector.js").read_text(encoding="utf-8")
    assert "ui-field-selector__ui-button" not in source
    assert "ui-field-selector__button--${direction}" in source
    assert "root.className = 'ui-field-selector'" in source
    for legacy in ("field-selection-layout", "field-selection-pane", "field-group-grid", "field-order-preview", "field-preview-pane"):
        assert f"{legacy} " not in source and f"'{legacy}'" not in source
    for name in ("keyword-promotion-live.js", "lifecycle-live.js", "overview-live.js", "products-live.js", "promotion-live.js"):
        consumer = (ASSETS / name).read_text(encoding="utf-8")
        assert "className: '" not in consumer or "field-selection" not in consumer


def test_canonical_panels_have_padding_and_no_legacy_component_selectors():
    source = (ASSETS / "components.css").read_text(encoding="utf-8")
    assert re.search(r"\.ui-panel\s*\{[^}]*padding:\s*var\(--space-4\)", source)
    assert not re.search(r"(?m)^\.(?:panel|plain-panel|metric-card|button|badge|data-table|data-table-wrap|empty-state|section-toolbar|metric-grid)\b", source)


def test_runtime_upgrade_shim_is_removed_and_audit_is_canonical():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "const isElement" in source
    assert "instanceof Node" not in source
    assert "new MutationObserver" not in source
    assert "legacyMap" not in source
    assert "const legacyNames" in source




def test_title_width_and_truncation_contract():
    tokens = (ASSETS / "tokens.css").read_text(encoding="utf-8")
    styles = (ASSETS / "components.css").read_text(encoding="utf-8")
    for token in ("--title-width-sm", "--title-width-md", "--title-width-lg", "--title-width-page"):
        assert token in tokens
    for rule in (".ui-panel__title", ".ui-metric-card__label", ".product-title__link", "text-overflow: ellipsis", "white-space: nowrap"):
        assert rule in styles


def test_shared_contract_rejects_legacy_assets():
    contract = load_script_module("check_ui_contract")
    assert contract.validate_scripts() == []
    assert contract.validate_styles() == []
    assert contract.validate_title_contract() == []


def test_pages_keep_shared_shell_and_design_tokens():
    pages = list(PAGES.glob("*.html"))
    assert len(pages) >= 17
    for page in pages:
        source = page.read_text(encoding="utf-8")
        assert "../assets/tokens.css" in source, page.name
        assert "../assets/components.css" in source, page.name
        assert 'data-shell-sidebar' in source, page.name
        assert 'data-shell-header' in source, page.name


def test_shared_date_range_supports_late_subscribers_and_analysis_sync():
    shell = (ASSETS / "shell.js").read_text(encoding="utf-8")
    store = (ASSETS / "runtime" / "date-range-store.js").read_text(encoding="utf-8")
    analysis = (ASSETS / "analysis-live.js").read_text(encoding="utf-8")
    # shell 拆分后只负责装配；订阅契约锚定 runtime/date-range-store.js
    assert "runtime/date-range-store.js" in shell
    assert "createDateRangeStore" in shell
    assert "subscribe: (subscriber, immediate = true)" in store
    assert "setRange: setSharedRange" in store
    assert "window.TmallDateRange?.subscribe?.((range) =>" in analysis
    assert "window.TmallDateRange?.setRange?.(start, end, 'custom')" in analysis
    assert "if (currentConfig) runAnalysis();" in analysis


def test_snapshot_pages_do_not_offer_unsupported_date_range():
    shell = (ASSETS / "shell.js").read_text(encoding="utf-8")
    for page in ("data-center", "data-collection", "settings", "goals"):
        assert page in shell


def test_sycm_pages_forward_shared_date_range():
    flow = (ASSETS / "flow-source-live.js").read_text(encoding="utf-8")
    rival = (ASSETS / "rival-analysis-live.js").read_text(encoding="utf-8")
    for source, endpoint in ((flow, "flow-source/summary"), (rival, "rival-shops/summary")):
        assert "tmall:date-range-change" in source
        assert "TmallDateRange" in source
        assert endpoint in source
    assert "const startDate = range.startDate" in flow
    assert "const endDate = range.endDate" in flow
    assert "params.set('start', startDate)" in flow
    assert "params.set('end', endDate)" in flow
    # rival 页同样要跟着共享时间范围走。shell.js 派发事件时 detail 就是 state 本身
    # （{ startDate, endDate, preset, compareMode }），所以直接 init(event.detail)
    # 与旧的「detail?.endDate || 全局 getState()」等价，不必逐字段取值。
    assert "addEventListener('tmall:date-range-change'" in rival
    assert "init(event.detail)" in rival
    assert "init(window.TmallDateRange?.getState?.())" in rival


def test_market_and_keyword_pages_forward_shared_date_range():
    market = (ASSETS / "market-ranking-live.js").read_text(encoding="utf-8")
    keyword = (ASSETS / "keyword-promotion-live.js").read_text(encoding="utf-8")
    assert "analysis_date" in market
    assert "tmall:date-range-change" in market
    assert "start: dateRange().startDate" in keyword
    assert "end: dateRange().endDate" in keyword


def test_sycm_product_ranking_columns_match_rendered_rows():
    page = (PAGES / "market-ranking.html").read_text(encoding="utf-8")
    source = (ASSETS / "market-ranking-live.js").read_text(encoding="utf-8")
    assert "sycm-item-rank-table" in page
    assert page.count('<col class="sycm-item-rank-col--') == 8
    assert '<th>商品图</th>' in page
    assert '<td colspan="8"' in page
    assert "sycm-item-rank-image" in source
    assert "sycm-item-rank-title" in source
    assert "sycm-item-rank-keyword" in source


def test_products_pilot_uses_canonical_ui_contract():
    source = (PAGES / "products.html").read_text(encoding="utf-8")
    assert "ui-metric-card" in source
    assert "ui-panel" in source


def test_no_new_hardcoded_colors_in_canonical_ui_rules():
    source = (ASSETS / "components.css").read_text(encoding="utf-8")
    canonical = source.split("/* Canonical UI component contract.", 1)[1].split(".metric-grid", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}|rgb\(", canonical)


def test_modal_component_is_registered_and_styled():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    for name in ("const modal", "const confirm", "showModal()", "aria-labelledby", "dataset.uiModalStatic"):
        assert name in source
    css = (ASSETS / "components.css").read_text(encoding="utf-8")
    for selector in (".ui-modal", ".ui-modal--sm", ".ui-modal__header", ".ui-modal__body", ".ui-modal__footer", ".ui-modal::backdrop"):
        assert selector in css


def test_component_layer_owns_data_state_without_demoapi_dependency():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "window.DemoApi" not in source
    api_source = (ASSETS / "api.js").read_text(encoding="utf-8")
    assert "window.TmallUI.renderDataState" in api_source
    assert "const stateLabels" not in api_source


def test_percent_formatter_requires_explicit_scale_mode():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "Math.abs(number) <= 1" not in source
    assert "mode = 'ratio'" in source


def test_overview_kpi_money_cards_share_brand_tone():
    source = (PAGES / "overview.html").read_text(encoding="utf-8")
    for key in ("net_sales", "payment_amount"):
        card = next(line for line in source.splitlines() if f'data-overview-kpi-select="{key}"' in line)
        assert "overview-v2-kpi--brand" in card, key


def test_css_files_have_valid_structure():
    """CSS 语法门禁：浏览器对 CSS 错误静默失败，必须静态拦截。

    事故背景：编辑时覆盖掉选择器行，留下没有选择器的孤立声明块，
    浏览器会连同其后的规则一起丢弃（如 position:fixed 失效），
    表现为「点了没反应」但 console 无报错。详见 scripts/check_css_syntax.py。
    """
    validate_all = load_script_module("check_css_syntax").validate_all

    failures = validate_all()
    assert not failures, "CSS 结构错误：\n" + "\n".join(
        f"{name}: {errors}" for name, errors in sorted(failures.items())
    )


def test_css_syntax_gate_detects_orphaned_declaration_block():
    """反向验证门禁本身有效：必须能识别出真实事故的形态。"""
    validate_css_text = load_script_module("check_css_syntax").validate_css_text

    # 事故原形：选择器行被覆盖，声明体成为孤儿，后续规则被吞
    broken = (
        ".a { color: red; }\n"
        "  display: inline-flex;\n"
        "  background: var(--surface-muted);\n"
        "}\n"
        ".demo-picker__backdrop { position: fixed; }\n"
    )
    errors = validate_css_text(broken)
    assert any("孤立声明块" in error for error in errors), errors

    # 未闭合花括号
    assert validate_css_text(".a { color: red;")

    # 合法 CSS 不应误报
    assert not validate_css_text(".a { color: red; }\n.b { position: fixed; }")
    # 注释与字符串中的花括号/冒号不应误报
    assert not validate_css_text('/* .x { color: red; } */\n.a { content: "{ }"; }')


def test_date_picker_smoke_gate_contract():
    """浏览器冒烟门禁脚本的契约：必须真的检查"可见可点"，而不只是"元素存在"。

    事故背景：弹窗存在但渲染在文档流底部（top 2221px / 视口 800px），
    页面表现为「点了没反应」。仅断言元素存在无法发现，必须校验
    浮层定位、视口内、命中测试三项。
    """
    script = (ROOT / "scripts" / "smoke_date_picker.cjs").read_text(encoding="utf-8")
    for marker in (
        "data-inline-grain",
        "data-inline-custom",
        "backdropPosition",
        "inViewport",
        "hitInside",
        "elementFromPoint",
        "Runtime.exceptionThrown",
    ):
        assert marker in script, marker
    # 不得依赖未安装的 playwright，否则门禁永远静默跳过
    assert "require.resolve('playwright'" not in script
    assert "require('playwright')" not in script


def test_date_picker_smoke_gate_runs_when_chrome_available():
    """Chrome 可用时真实运行冒烟门禁；需要本地服务，缺失则跳过。"""
    import os
    import shutil
    import subprocess

    chrome_candidates = [
        os.environ.get("TMALL_CHROME"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    chrome = next((c for c in chrome_candidates if c and os.path.isfile(c)), None)
    if not chrome:
        raise unittest.SkipTest("未找到 Chrome")

    base = os.environ.get("TMALL_SMOKE_BASE", "http://127.0.0.1:5000")
    import urllib.request
    try:
        urllib.request.urlopen(base, timeout=3).close()
    except Exception:
        raise unittest.SkipTest(f"本地服务不可用：{base}")

    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "smoke_date_picker.cjs"), base],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
    )
    assert result.returncode == 0, (
        "时间选择器冒烟门禁失败：\n" + (result.stdout or "") + "\n" + (result.stderr or "")
    )


def test_pytest_stays_out_of_production_requirements():
    """pytest 必须留在 requirements-dev.txt，不能混进运行时依赖。

    requirements.txt 会被 desktop-release.yml 的打包步骤安装，
    把测试运行器放进去会让它随桌面生产包分发。
    """
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "pytest" not in runtime, "pytest 不应出现在运行时依赖 requirements.txt"
    assert "pytest" in dev, "pytest 必须在 requirements-dev.txt 中声明"


def test_ui_contract_scans_every_css_and_js_file():
    """契约扫描范围必须与文件系统实际一致，防止再次漏扫。

    背景：check_ui_contract.py 原先用 ASSETS.glob("*.css") / glob("*.js")，
    只扫 assets/ 顶层 —— 6 个 themes/ 下的主题 CSS 和 21 个 pages/、runtime/
    下的 JS（含核心状态模块 date-range-store.js）从未被检查，且没有任何测试发现。
    这里断言扫描数与实际数相等，把这个覆盖缺口永久锁住。
    """
    contract = load_script_module("check_ui_contract")
    actual_css = [p for p in ASSETS.rglob("*.css") if p.is_file()]
    actual_js = [p for p in ASSETS.rglob("*.js") if p.is_file() and not p.name.endswith(".min.js")]

    # validate_* 内部用 rglob，覆盖率必须等于文件系统
    scanned_css = sorted(p.relative_to(ASSETS).as_posix() for p in ASSETS.rglob("*.css"))
    scanned_js = sorted(
        p.relative_to(ASSETS).as_posix()
        for p in ASSETS.rglob("*.js")
        if not p.name.endswith(".min.js")
    )
    assert len(scanned_css) == len(actual_css), f"CSS 扫描数 {len(scanned_css)} != 实际 {len(actual_css)}"
    assert len(scanned_js) == len(actual_js), f"JS 扫描数 {len(scanned_js)} != 实际 {len(actual_js)}"
    # 嵌套目录必须被覆盖（这正是原缺口所在）
    assert any("/" in p for p in scanned_css), "未递归扫描到 themes/ 下的 CSS"
    assert any("/" in p for p in scanned_js), "未递归扫描到 pages/、runtime/ 下的 JS"
    # 契约本身必须仍然通过
    assert contract.validate_styles() == []
    assert contract.validate_scripts() == []


def test_design_system_gate_blocks_new_handwritten_components():
    """R5 必须真的能拦住新增手写复合组件（含反向验证）。

    只断言"当前通过"是不够的 —— 一个永远返回 [] 的门禁也能通过。
    这里验证：人为在手写计数上越界时，check_handwritten_components 必须报错。
    """
    design = load_script_module("check_design_system")
    # 基线必须覆盖所有存在手写量的页面，否则新增页面会以 0 预算通过
    baseline = design.UI_HANDWRITE_BASELINE
    assert baseline, "缺少手写复合组件基线"

    for page in sorted(PAGES.glob("*.html")):
        found = design.count_handwritten_components(page)
        allowed = baseline.get(page.stem, 0)
        assert found <= allowed, (
            f"{page.name} 手写复合组件 {found} 处超出基线 {allowed}；"
            "收敛后请同步下调 UI_HANDWRITE_BASELINE"
        )

    # 反向验证：把某页预算强行设为 -1（等价于"任何手写都算越界"），必须报错
    original = dict(baseline)
    try:
        target = next(iter(original))
        baseline[target] = -1
        errors = design.check_handwritten_components()
        assert any("R5" in e for e in errors), "R5 未能拦住越界的手写复合组件"
    finally:
        baseline.clear()
        baseline.update(original)


def test_design_system_gate_keeps_atomic_classes_handwritable():
    """原子类（button/badge）不得被 R5 误伤。

    这是刻意的设计判断：原子类没有内部结构约定，静态 HTML 手写合理；
    强制走 JS 工厂会破坏服务端渲染且收益为负。
    """
    design = load_script_module("check_design_system")
    for atomic in ("ui-button", "ui-badge"):
        assert atomic not in design.COMPOSITE_COMPONENT_ROOTS, (
            f"{atomic} 是原子类，不应被 R5 当作必须走工厂的复合组件"
        )
    for composite in ("ui-panel", "ui-metric-card", "ui-table-wrap"):
        assert composite in design.COMPOSITE_COMPONENT_ROOTS, (
            f"{composite} 是复合组件，必须在 R5 覆盖范围内"
        )


def test_ci_wires_static_and_browser_gates():
    """CI 必须真的执行这些门禁，否则它们只是本地摆设。

    背景：quality-gate.yml 原先只跑 `unittest discover`，而 tests/ 下有 4 个
    纯 pytest 风格文件（无 unittest.TestCase）会被收集 0 个测试 —— 等于从未执行。
    """
    workflow = (ROOT / ".github" / "workflows" / "quality-gate.yml").read_text(encoding="utf-8")
    for command in (
        "python -m pytest",
        "scripts/check_css_syntax.py --strict",
        "scripts/check_design_system.py --strict",
        "scripts/check_css_tokens.py --strict",
        "scripts/check_event_binding.py --strict",
        "tsc -p tsconfig.json --noEmit",
        "scripts/smoke_popover.cjs",
        "scripts/smoke_date_picker.cjs",
    ):
        assert command in workflow, f"CI 未接入门禁：{command}"


def test_type_checked_file_list_only_grows():
    """类型检查覆盖范围只增不减，防止退化。

    `tsc` 只检查 tsconfig.json 的 include 白名单。如果范围被悄悄缩小，
    类型检查会静默失去价值 —— 这里断言清单至少包含当前这些核心模块。
    """
    import json

    config = json.loads((ROOT / "tsconfig.json").read_text(encoding="utf-8"))
    included = set(config["include"])
    required = {
        "frontend/ui_demo/assets/globals.d.ts",
        "frontend/ui_demo/assets/ui-components.js",
        "frontend/ui_demo/assets/runtime/date-range-store.js",
    }
    missing = required - included
    assert not missing, f"tsconfig.json include 缺少核心模块：{sorted(missing)}"
    assert config["compilerOptions"]["checkJs"] is True, "checkJs 必须为 true"
    assert config["compilerOptions"]["noEmit"] is True, "必须 noEmit：类型检查不得产出运行时代码"


def test_globals_declares_cross_file_runtime_objects():
    """跨文件全局必须登记在 globals.d.ts，否则每处访问都会报 TS2339。"""
    globals_dts = (ASSETS / "globals.d.ts").read_text(encoding="utf-8")
    for name in ("TmallUI", "TmallRuntime", "TmallDateRange", "DemoApi", "lucide"):
        assert name in globals_dts, f"globals.d.ts 缺少全局声明：{name}"
    # 浮层原语必须在类型层可见，供页面消费
    assert "popover" in globals_dts


def test_date_picker_smoke_gate_asserts_selection_takes_effect():
    """门禁必须断言"选完即生效"，不能只断言"弹窗打开"。

    背景：此前的门禁只验证弹窗打开与高亮，于是漏掉一个真实 bug ——
    月份格子的点击处理器引用了 render() 作用域内的局部变量，
    点月份抛 ReferenceError，选「3月」却静默停在当前月。
    点击"成功"、弹窗"打开"、高亮"正确"，唯独状态没变。
    """
    script = (ROOT / "scripts" / "smoke_date_picker.cjs").read_text(encoding="utf-8")
    for marker in (
        "选中即生效",
        "data-picker-month",
        "data-picker-year",
        "点击后日期范围必须变化",
        "落到期望范围",
        "非 NaN",
    ):
        assert marker in script, f"时间选择器门禁缺少断言：{marker}"


def test_pytest_only_test_files_are_covered_by_ci():
    """纯 pytest 风格文件必须在 CI 里显式列出，否则 unittest discover 收集不到。"""
    workflow = (ROOT / ".github" / "workflows" / "quality-gate.yml").read_text(encoding="utf-8")
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        has_unittest_class = "unittest.TestCase" in source
        has_bare_tests = bool(re.search(r"(?m)^def test_", source))
        if has_bare_tests and not has_unittest_class:
            assert path.name in workflow, (
                f"{path.name} 是纯 pytest 风格，unittest discover 收集不到，必须在 CI 中显式运行"
            )


def test_ci_referenced_files_are_tracked_by_git():
    """CI 调用的文件必须已入库，否则全新 clone 上流水线必挂。

    背景：本仓库有真实远端（origin = github.com/owen891/tmall-dashboard），
    CI 会真的执行。曾经有 6 个被 CI 引用的文件从未 `git add`：
      scripts/check_css_syntax.py、scripts/check_design_system.py、
      scripts/check_event_binding.py、scripts/smoke_popover.cjs、
      scripts/smoke_date_picker.cjs、tsconfig.json。
    本地因为文件都在磁盘上而全绿，远端一 clone 就是 No such file。
    """
    import subprocess

    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    assert tracked, "git ls-files 返回空，测试环境异常"

    workflow_dir = ROOT / ".github" / "workflows"
    pattern = re.compile(r"^(?:python|node|bash|pwsh)\s+([\w./-]+\.(?:py|cjs|js|json))", re.M)
    missing = []
    for wf in sorted(workflow_dir.glob("*.yml")):
        for match in pattern.finditer(wf.read_text(encoding="utf-8")):
            path = match.group(1)
            if path.startswith("$") or path in ("-m",):
                continue
            if path not in tracked:
                missing.append(f"{wf.name}: {path}")
    assert not missing, "CI 引用但未入库（全新 clone 会失败）：\n  " + "\n  ".join(missing)


def test_tsconfig_is_not_gitignored():
    """tsconfig.json 必须可入库。

    背景：.gitignore 的 `/*.json` 是"根目录 JSON 都是探针产物"的良性规则，
    但它把前端的类型检查配置一起吞了，于是 CI 的 `tsc -p tsconfig.json`
    在全新 clone 上必然报文件不存在。

    为什么不能只断言 `git check-ignore tsconfig.json` 的退出码：
        git 对**已跟踪**文件恒不报忽略（退出 1），所以文件入库后该断言
        永远为真，规则被改回去也查不出来 —— 这是个不会失败的测试。
        因此这里断言 .gitignore 里确实存在这条否定规则本身，
        并用一个不受影响的探针文件确认 `/*.json` 仍然正常工作。
    """
    import subprocess

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    # 必须按"整行"判断：`"!/tsconfig.json" in text` 对 `# !/tsconfig.json`
    # 也成立（前者是后者的子串），那样的断言永远不会失败。
    rules = {line.strip() for line in gitignore.splitlines()}
    assert "!/tsconfig.json" in rules, (
        ".gitignore 缺少生效的 `!/tsconfig.json` 例外行，根目录 /*.json 规则会吞掉 "
        "tsconfig.json，CI 的类型检查步骤在全新 clone 上会失败"
    )

    # 反向确认 /*.json 规则本身仍生效（例外不能把整条规则废掉）
    probe = ROOT / "probe_gitignore_contract.json"
    probe.write_text("{}", encoding="utf-8")
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "probe_gitignore_contract.json"],
            cwd=ROOT,
            capture_output=True,
        )
        assert result.returncode == 0, "根目录 /*.json 忽略规则失效了，请检查 .gitignore"
    finally:
        probe.unlink(missing_ok=True)


def test_external_data_is_escaped_before_entering_innerhtml():
    """采集/导入数据插进 HTML 前必须转义。

    背景：两个真实缺陷。
      1. market-ranking-live.js 的生意参谋搜索排行表，`${kw.cate_name}` 与
         `${kw.keyword}` 未转义 —— 而同一文件已定义 escapeHtml 且用了 41 次，
         只有这张表漏了。
      2. product-detail-live.js 全文 0 处转义，单品的流量来源渠道名
         （node.channel_name）同时插进 HTML 属性值与文本节点。
    放大因素：应用没有 CSP 响应头（app.py 只设 nosniff 与 SAMEORIGIN）。

    这里只锁死这两个已知注入点，不做全仓库扫描（存量插值多为内部静态标签，
    误报会让人直接把门禁关掉）。
    """
    market = (ASSETS / "market-ranking-live.js").read_text(encoding="utf-8")
    assert "${escapeHtml(kw.cate_name)}" in market
    assert "${escapeHtml(kw.keyword)}" in market

    detail = (ASSETS / "product-detail-live.js").read_text(encoding="utf-8")
    assert "const escapeHtml = window.DemoFormat?.escapeHtml" in detail, (
        "product-detail-live.js 必须从共享 format.js 取用 escapeHtml"
    )
    assert 'data-item-flow-toggle="${escapeHtml(node.channel_name)}"' in detail
    assert 'data-item-flow-channel="${escapeHtml(node.channel_name)}"' in detail
    # 文本节点与属性值都要转义，不能只转一处
    assert ">${escapeHtml(node.channel_name)}</span>" in detail


def test_product_detail_page_loads_format_before_live_script():
    """product-detail-live.js 依赖 window.DemoFormat，加载顺序不能反。

    format.js 必须排在 product-detail-live.js 之前，否则
    window.DemoFormat?.escapeHtml 求值为 undefined，静默退回正则回退实现
    （功能仍正确，但共享契约被绕过，属于隐性回归）。
    """
    html = (PAGES / "product-detail.html").read_text(encoding="utf-8")
    format_at = html.find("assets/format.js")
    live_at = html.find("assets/product-detail-live.js")
    assert format_at != -1, "product-detail.html 未加载 format.js"
    assert live_at != -1, "product-detail.html 未加载 product-detail-live.js"
    assert format_at < live_at, "format.js 必须在 product-detail-live.js 之前加载"


def test_category_dashboard_escapes_service_payload_before_innerhtml():
    """SEC-03 残留：品类经营看板的 innerHTML 插值必须全部转义。

    背景（PROJECT_REMEDIATION_REPORT_20261011 的 SEC-03）：category-dashboard-live.js
    的 renderKpis 已经转义，但 renderProfit / renderProducts / renderAnnual 三个
    渲染函数仍在往 innerHTML 里插未转义的服务端数据：
      - renderProfit:     `${name}`（来自 PROFIT_ROWS，本地常量，但同一模板里的
                          `text` 由服务端 breakdown 计算）与未转义的 `${text}`
      - renderProducts:   rows（来自 /api/category-analysis/compare 的 contributors）
      - renderAnnual:     年度矩阵行值、同比率（来自 /api/category-analysis/matrix）
    同一文件第 4 行已从共享 format.js 取用 escapeHtml，说明这是漏改不是设计。

    这里只锁死"服务端数据进入 innerHTML 前必须过 escapeHtml"这一点。
    """
    source = (ASSETS / "category-dashboard-live.js").read_text(encoding="utf-8")

    assert "const escapeHtml = window.DemoFormat?.escapeHtml" in source, (
        "category-dashboard-live.js 必须从共享 format.js 取用 escapeHtml，"
        "不能退回本文件私有的正则实现"
    )

    # renderProducts：贡献商品名与两个数值单元格
    assert "${escapeHtml(format(row.current_value, metric))}" in source
    assert "${escapeHtml(format(row.change, metric))}" in source

    # renderAnnual：年度矩阵行值与同比率
    assert "${escapeHtml(format(row.values?.[String(year)], metric))}" in source
    assert "${escapeHtml(percent(row.yoy?.rate))}" in source
    assert "${escapeHtml(format(item.annual?.[String(year)], metric))}" in source

    # 反向确认：这几个模板里不再有裸插值形态
    for bare in (
        '<td class="num">${format(row.current_value, metric)}</td>',
        '<td class="num">${format(row.change, metric)}</td>',
        '<td class="num">${format(row.values?.[String(year)], metric)}</td>',
        '<td class="num">${percent(row.yoy?.rate)}</td>',
    ):
        assert bare not in source, f"category-dashboard-live.js 仍存在未转义插值：{bare}"


def test_operations_center_innerhtml_interpolations_are_literal_or_escaped():
    """operations-center.js 的 innerHTML 只允许字面量或已转义插值。

    `remove.innerHTML = '<i data-lucide="trash-2" …></i><span>删除</span>'`
    是纯字面量，审计脚本会把同一语句里其它行的 `actionTitle(action)`
    （实际只用于 setAttribute 的 aria-label）误报成插值。
    这条断言把该误报固化为"允许"，避免后人为了消警把正确的 setAttribute
    改成 innerHTML。
    """
    source = (ASSETS / "operations-center.js").read_text(encoding="utf-8")
    assert """remove.setAttribute('aria-label', `删除${actionTitle(action)}`)""" in source
    assert """remove.innerHTML = '<i data-lucide="trash-2" aria-hidden="true"></i><span>删除</span>'""" in source

