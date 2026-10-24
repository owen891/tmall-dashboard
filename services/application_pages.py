"""Single source of truth for the routable page set.

`app.py` renders these through `/<page>`; `services/page_capability_service.py`
asserts that every routable page is also registered as a capability page.
Keeping the set in a dependency-free module lets both sides import it without a
cycle — importing `app` from a service would be worse than circular, because
`python app.py` runs the file as `__main__` and `import app` would build a
second, unrelated application object.
"""
from pathlib import Path


# Pages served by `/<page>` -> `pages/<page>.html`. Private-edition pages
# (collector console etc.) are contributed by services.private_pages_registry,
# which ships only with private deployments — the public source carries none.
_PUBLIC_APPLICATION_PAGES = frozenset({
    'overview',
    'analysis',
    'category-dashboard',
    'products',
    'promotion',
    'promotion-matrix',
    'new-products',
    'market-ranking',
    'lifecycle',
    'reviews',
    'data-center',
    'settings',
    'goals',
    'flow-source',
    'rival-analysis',
    'component-catalog',
    'creative-board',
    'period-review',
})


def _private_page_keys():
    try:
        from services.private_pages_registry import PRIVATE_PAGE_KEYS
    except ImportError:
        return frozenset()
    return frozenset(PRIVATE_PAGE_KEYS)


APPLICATION_PAGES = _PUBLIC_APPLICATION_PAGES | _private_page_keys()


# The capability registry keys a page by `body[data-page]`, which is not always
# the URL segment: `component-catalog.html` declares `data-page="catalog"` and
# queries `/api/page-capabilities?page=catalog`.
REGISTRY_KEY_OVERRIDES = {
    'component-catalog': 'catalog',
}


# Pages reachable through a dedicated rule instead of `/<page>`.
DEDICATED_ROUTE_PAGES = frozenset({
    'product-detail',  # served by /products/<product_id>
})


# Legacy paths kept as redirects so old bookmarks keep working. They stay
# registered as capability pages until the page files are removed.
LEGACY_REDIRECT_PAGES = {
    'compare': '/reviews',
    'manage': '/settings',
}


def registry_keys():
    """Every page key the capability registry is expected to declare."""
    return frozenset(
        REGISTRY_KEY_OVERRIDES.get(page, page) for page in APPLICATION_PAGES
    ) | DEDICATED_ROUTE_PAGES


def routable_pages():
    """Routable pages that actually exist on disk.

    Private-edition deployments carry extra pages (e.g. the collector console);
    a public checkout simply does not contain those files, so the route and the
    capability catalog disappear with them. The static set above stays the
    registry superset; availability is filesystem-driven.
    """
    pages_dir = Path(__file__).resolve().parents[1] / 'frontend' / 'ui_demo' / 'pages'
    return frozenset(page for page in APPLICATION_PAGES if (pages_dir / f'{page}.html').is_file())
