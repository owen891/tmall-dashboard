from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "ui_demo" / "assets"
PAGES = ROOT / "frontend" / "ui_demo" / "pages"


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
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_ui_contract import validate_page

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


    for name in ("keyword-promotion-live.js", "lifecycle-live.js", "overview-live.js", "products-live.js", "promotion-live.js"):
        source = (ASSETS / name).read_text(encoding="utf-8")
        assert "TmallUI.fieldSelector" in source, name
        assert "DemoFieldSelector" not in source, name


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
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_ui_contract import validate_scripts, validate_styles, validate_title_contract
    assert validate_scripts() == []
    assert validate_styles() == []
    assert validate_title_contract() == []


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
    analysis = (ASSETS / "analysis-live.js").read_text(encoding="utf-8")
    assert "subscribe: (subscriber, immediate = true)" in shell
    assert "setRange: setSharedRange" in shell
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
    assert "window.TmallUI?.renderDataState" in api_source


def test_percent_formatter_requires_explicit_scale_mode():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "Math.abs(number) <= 1" not in source
    assert "mode = 'ratio'" in source


def test_overview_kpi_money_cards_share_brand_tone():
    source = (PAGES / "overview.html").read_text(encoding="utf-8")
    for key in ("net_sales", "payment_amount"):
        card = next(line for line in source.splitlines() if f'data-overview-kpi-select="{key}"' in line)
        assert "overview-v2-kpi--brand" in card, key
