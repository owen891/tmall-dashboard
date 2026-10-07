"""Single source of truth for the routable page set.

`app.py` renders these through `/<page>`; `services/page_capability_service.py`
asserts that every routable page is also registered as a capability page.
Keeping the set in a dependency-free module lets both sides import it without a
cycle — importing `app` from a service would be worse than circular, because
`python app.py` runs the file as `__main__` and `import app` would build a
second, unrelated application object.
"""


# Pages served by `/<page>` -> `pages/<page>.html`.
APPLICATION_PAGES = frozenset({
    'overview',
    'analysis',
    'category-dashboard',
    'products',
    'promotion',
    'keyword-promotion',
    'new-products',
    'market-ranking',
    'lifecycle',
    'reviews',
    'data-center',
    'settings',
    'goals',
    'flow-source',
    'rival-analysis',
    'data-collection',
    'component-catalog',
    'creative-board',
    'period-review',
    'core-product-analysis',
})


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
