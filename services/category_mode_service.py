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
    if category_mode == SOCK_MODE:
        return SOCK_LABEL
    try:
        from services.settings_service import settings_service
        for mode in settings_service.get().get('category_modes', []):
            if mode.get('value') == category_mode:
                return mode.get('shop_label') or None
    except Exception:
        pass
    return category_mode


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
    """Configured category definitions plus labels discovered in imported data."""
    try:
        with get_db() as connection:
            rows = connection.execute(
                "SELECT DISTINCT shop_label FROM products WHERE shop_label != '' ORDER BY shop_label"
            ).fetchall()
    except Exception:
        rows = []
    labels = [r['shop_label'] for r in rows]
    try:
        from services.settings_service import settings_service
        configured = settings_service.get().get('category_modes', [])
    except Exception:
        configured = []
    result = [
        {'value': item['value'], 'label': item['label'], 'shop_label': item.get('shop_label'), 'enabled': item.get('enabled', True), 'system': item.get('system', False)}
        for item in configured
    ]
    values = {item['value'] for item in result}
    mapped_labels = {item.get('shop_label') for item in result if item.get('shop_label')}
    for label in labels:
        if label and label not in values and label not in mapped_labels and label != SOCK_LABEL:
            result.append({'value': label, 'label': label, 'shop_label': label, 'enabled': True, 'system': False})
            values.add(label)
            mapped_labels.add(label)
    if not result:
        result = [{'value': 'all', 'label': '全部品类', 'shop_label': None, 'enabled': True, 'system': True}, {'value': SOCK_MODE, 'label': SOCK_LABEL, 'shop_label': SOCK_LABEL, 'enabled': True, 'system': True}]
    return result
