# -*- coding: utf-8 -*-
"""Category mode (品类模式) support.

The dashboard can be scoped to a product label from the BI 商品标签 column
(e.g. 标品袜子). The frontend sends `category_mode` on API requests:

    all        -> no filtering (backward compatible default)
    sock       -> short alias for 标品袜子
    <label>    -> exact BI label value (supports multi-label values)

The service-side default is `all`, so existing callers without the parameter
keep their behaviour; the frontend decides what the user sees by default.
"""
from __future__ import annotations

from flask import has_request_context, request

from db import get_db

SOCK_MODE = 'sock'
SOCK_LABEL = '标品袜子'
ALL_MODES = ('all', SOCK_MODE)
CATEGORY_MODE_PARAM = 'category_mode'


def requested_category_mode() -> str | None:
    """Read category_mode from the request (None when absent/empty)."""
    if not has_request_context():
        return None
    raw = (request.args.get(CATEGORY_MODE_PARAM) or '').strip()
    return raw or None


def mode_to_label(category_mode: str | None) -> str | None:
    """Resolve a category_mode value to the actual shop_label value, or None for all."""
    if not category_mode or category_mode == 'all':
        return None
    return SOCK_LABEL if category_mode == SOCK_MODE else category_mode


def shop_label_filter(filters: dict | None = None) -> tuple[str | None, list]:
    """Return (where_sql, params) for the category mode already present in filters.

    Uses filters['shop_label'] when set (the API layer resolves category_mode into
    this key). Multi-label values (e.g. '标品袜子,平销商品') match by token.

    Returns (None, []) when no filtering applies.
    """
    filters = filters or {}
    label = (filters.get('shop_label') or '').strip()
    if not label or label == 'all':
        return None, []
    clause = "(p.shop_label = ? OR instr(',' || p.shop_label || ',', ',' || ? || ',') > 0)"
    return clause, [label, label]


def category_filters_from_request() -> dict:
    """API-layer helper: resolve category_mode into a filters dict."""
    mode = requested_category_mode()
    label = mode_to_label(mode)
    if not label:
        return {}
    return {'shop_label': label}


def available_labels() -> list[dict]:
    """Distinct non-empty shop_label values for the settings/UI dropdown."""
    try:
        with get_db() as connection:
            rows = connection.execute(
                "SELECT DISTINCT shop_label FROM products WHERE shop_label != '' ORDER BY shop_label"
            ).fetchall()
    except Exception:
        rows = []
    labels = [r['shop_label'] for r in rows]
    return [
        {'value': 'all', 'label': '全部品类'},
        {'value': SOCK_MODE, 'label': '标品袜子'},
        *({'value': label, 'label': label} for label in labels if label != SOCK_LABEL),
    ]
