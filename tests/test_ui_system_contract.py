from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "ui_demo" / "assets"
PAGES = ROOT / "frontend" / "ui_demo" / "pages"


def test_canonical_ui_registry_exposes_required_components():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    for name in ("format", "button", "badge", "emptyState", "dataState", "metricCard", "metricGrid", "panel", "pageHeader", "filterToolbar", "table", "setState", "fieldSelector"):
        assert name in source
    for legacy, canonical in (("button", "ui-button"), ("metric-card", "ui-metric-card"), ("panel", "ui-panel"), ("empty-state", "ui-empty-state"), ("demo-page__intro", "ui-page-header"), ("data-table", "ui-data-table")):
        assert f"{legacy}: '{canonical}'" in source or f"'{legacy}': '{canonical}'" in source


def test_ui_audit_is_exposed():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "const audit" in source
    assert "api.audit = audit" in source


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


def test_legacy_panels_keep_padding_while_structured_panels_do_not():
    source = (ASSETS / "components.css").read_text(encoding="utf-8")
    assert re.search(r"\.panel\s*\{[^}]*padding:\s*var\(--space-4\)", source)
    assert re.search(r"\.ui-panel\s*\{(?![^}]*padding:)\s*[^}]*border:", source)
    assert len(re.findall(r"(?m)^\.ui-panel\s*\{", source)) == 1


def test_runtime_upgrade_handles_dynamic_nodes_without_global_node_constructor():
    source = (ASSETS / "ui-components.js").read_text(encoding="utf-8")
    assert "const isElement" in source
    assert "instanceof Node" not in source
    assert "new MutationObserver" in source


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
    assert "if (currentConfig) runAnalysis();" in analysis
    assert "window.TmallDateRange?.setRange?.(start, end, 'custom')" in analysis


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
