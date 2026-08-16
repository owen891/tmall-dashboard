"""Request-scope guards for legacy tables that are still single-shop."""

from api.api_response import failure
from db import get_shop_id


def reject_legacy_shop_scope(domain):
    """Reject a non-default shop before reading a table without shop_id."""
    shop_id = get_shop_id()
    if shop_id and shop_id != 'default':
        return failure(
            'UNSUPPORTED_SCOPE',
            f'{domain} 当前仍使用单店旧表，不支持 shop_id={shop_id}；请先完成店铺迁移',
            status=422,
        )
    return None
