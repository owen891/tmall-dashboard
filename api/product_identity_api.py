from flask import Blueprint, request

from api.api_response import failure, json_object, success
from db import get_db
from repos.audit_repo import AuditRepo
from services.product_identity_service import (
    list_identity_candidates,
    resolve_identity,
)
from services.shop_scope_service import audit_identity, current_request_shop_id


product_identity_bp = Blueprint('product_identity', __name__)


@product_identity_bp.route('/api/product-identities', methods=['GET'])
def get_product_identities():
    status = request.args.get('status', 'unresolved')
    try:
        limit = request.args.get('limit', 100, type=int) or 100
        offset = request.args.get('offset', 0, type=int) or 0
        with get_db() as connection:
            data = list_identity_candidates(
                connection,
                shop_id=current_request_shop_id(),
                status=status,
                limit=limit,
                offset=offset,
            )
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(
        data,
        availability='available' if data['items'] else 'no-data',
        evidence_level='full' if data['items'] else 'insufficient',
        filters={
            'shop_id': data['shop_id'],
            'status': data['status'],
            'limit': data['limit'],
            'offset': data['offset'],
        },
        evidence=[{'source': 'product_identity_map', 'row_count': data['total']}],
        limitations=['身份绑定必须由运营明确确认，系统不会自动猜测商品'] if data['items'] else [],
    )


@product_identity_bp.route('/api/product-identities/<external_product_id>/resolve', methods=['POST'])
def resolve_product_identity(external_product_id):
    data = json_object(request)
    canonical_product_id = str(data.get('canonical_product_id') or '').strip()
    if not canonical_product_id:
        return failure('VALIDATION_ERROR', '缺少 canonical_product_id', status=422)
    operator, reason = audit_identity(data, '确认推广外部商品身份')
    try:
        with get_db() as connection:
            result = resolve_identity(
                connection,
                shop_id=current_request_shop_id(),
                external_product_id=external_product_id,
                canonical_product_id=canonical_product_id,
                operator=operator,
                reason=reason,
            )
            AuditRepo.record(
                'product_identity',
                f"{current_request_shop_id()}:{external_product_id}",
                'resolve',
                operator,
                reason,
                result['before'],
                result['after'],
                connection=connection,
            )
            connection.commit()
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    except LookupError as error:
        return failure('NOT_FOUND', str(error), status=404)
    return success(
        {'item': result['after']},
        evidence_level='full',
        evidence=[{'source': 'product_identity_map', 'action': 'resolve', 'row_count': 1}],
        assumptions=['仅绑定到已存在的 products.product_id，不自动创建商品主档'],
    )
