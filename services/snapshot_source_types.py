"""Authoritative snapshot source type registry.

The user-exported 商品总览 workbook is registered under a deployment-specific
source_type string. That literal is a brand token, so it must not appear in
the public tree: the public checkout uses the neutral default below, while a
private deployment supplies its own value through
`services.private_source_types` (not tracked by this repository).

The value is also persisted in the database (``daily_data_observations`` and
``import_batches``). Renaming it therefore has to happen as a migration, not
as a code edit — see ``scripts/rename_snapshot_source_type.py``.
"""

try:  # Private deployment override (absent in the public checkout).
    from services.private_source_types import (
        SNAPSHOT_SOURCE_PREFIX as _PRIVATE_SNAPSHOT_PREFIX,
        SNAPSHOT_SOURCE_TYPES as _PRIVATE_SNAPSHOT_TYPES,
    )
except ImportError:  # Public checkout: neutral, brand-free identifiers.
    _PRIVATE_SNAPSHOT_PREFIX = 'snapshot_bi_'
    _PRIVATE_SNAPSHOT_TYPES = ('snapshot_bi_product_day',)

# Prefix shared by every snapshot source_type written from a 商品总览 workbook.
SNAPSHOT_SOURCE_PREFIX = _PRIVATE_SNAPSHOT_PREFIX

# Snapshot source types whose present fields outrank older product/day,
# promotion and DMP imports for the same product/date. Fields absent from the
# snapshot still fall through to the normal precedence rules.
AUTHORITATIVE_SNAPSHOT_SOURCE_TYPES = frozenset(_PRIVATE_SNAPSHOT_TYPES)

# Alias kept for callers that only need the enumeration.
SNAPSHOT_SOURCE_TYPES = AUTHORITATIVE_SNAPSHOT_SOURCE_TYPES
