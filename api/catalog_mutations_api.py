from flask import Blueprint, request

from api.api_response import failure, success
from db import get_db
from repos.audit_repo import AuditRepo


catalog_mutations_bp = Blueprint('catalog_mutations', __name__)

ALLOWED_PRODUCT_FIELDS = {'tier', 'style', 'scene', 'manager', 'remark'}


def _payload():
    return request.get_json(silent=True) or {}


def _operator_reason(data, default_reason):
    return data.get('operator') or data.get('actor') or 'admin', data.get('reason') or default_reason


def _success(data, *, source, action, row_count=1, status=200, unknowns=None):
    return success(
        data,
        status=status,
        availability='available' if row_count else 'no-data',
        evidence_level='full' if row_count else 'insufficient',
        evidence=[{'source': source, 'action': action, 'row_count': row_count}],
        unknowns=list(unknowns or []),
    )


@catalog_mutations_bp.route('/api/products/<product_id>/metadata', methods=['PUT'])
def update_product_metadata(product_id):
    data = _payload()
    field = str(data.get('field') or '').strip()
    if field not in ALLOWED_PRODUCT_FIELDS:
        return failure('VALIDATION_ERROR', f'不允许修改字段「{field}」', status=422)
    if not product_id:
        return failure('VALIDATION_ERROR', '缺少 product_id', status=422)
    value = data.get('value')
    if value is None:
        return failure('VALIDATION_ERROR', '缺少 value', status=422)
    value = str(value).strip()
    operator, reason = _operator_reason(data, f'修改商品{field}')

    with get_db() as connection:
        row = connection.execute(
            f'SELECT product_id, {field} FROM products WHERE product_id = ?',
            (product_id,),
        ).fetchone()
        if row is None:
            return failure('NOT_FOUND', '商品不存在', status=404)
        before = row[field]
        connection.execute(
            f'UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (value, product_id),
        )
        AuditRepo.record(
            'product', product_id, 'update_metadata', operator, reason,
            {field: before}, {field: value}, connection=connection,
        )
        connection.commit()

    return _success(
        {'product_id': product_id, 'field': field, 'value': value},
        source='products', action='update_metadata',
    )


@catalog_mutations_bp.route('/api/products/<product_id>/star', methods=['POST'])
def set_product_star(product_id):
    data = _payload()
    operator, reason = _operator_reason(data, '更新商品收藏状态')
    with get_db() as connection:
        row = connection.execute(
            'SELECT starred FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if row is None:
            return failure('NOT_FOUND', '商品不存在', status=404)
        current = int(row['starred'] or 0)
        if 'starred' in data:
            starred = 1 if int(data.get('starred') or 0) else 0
        else:
            starred = 0 if current else 1
        connection.execute(
            'UPDATE products SET starred = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (starred, product_id),
        )
        AuditRepo.record(
            'product', product_id, 'set_starred', operator, reason,
            {'starred': current}, {'starred': starred}, connection=connection,
        )
        connection.commit()
    return _success(
        {'product_id': product_id, 'starred': starred},
        source='products', action='set_starred',
    )


@catalog_mutations_bp.route('/api/products/batch-update', methods=['POST'])
def batch_update_products():
    data = _payload()
    field = str(data.get('field') or '').strip()
    product_ids = [str(item) for item in (data.get('product_ids') or []) if str(item)]
    value = data.get('value')
    if field not in {'tier', 'style'}:
        return failure('VALIDATION_ERROR', '批量更新只允许 tier 或 style', status=422)
    if not product_ids or value is None or not str(value).strip():
        return failure('VALIDATION_ERROR', '商品ID列表和批量值不能为空', status=422)
    value = str(value).strip()
    operator, reason = _operator_reason(data, f'批量修改{field}')

    with get_db() as connection:
        placeholders = ','.join('?' for _ in product_ids)
        rows = connection.execute(
            f'SELECT product_id, {field} FROM products WHERE product_id IN ({placeholders})',
            product_ids,
        ).fetchall()
        for row in rows:
            AuditRepo.record(
                'product', row['product_id'], 'batch_update', operator, reason,
                {field: row[field]}, {field: value}, connection=connection,
            )
        if rows:
            connection.execute(
                f'UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id IN ({placeholders})',
                [value, *product_ids],
            )
        connection.commit()

    missing = sorted(set(product_ids) - {row['product_id'] for row in rows})
    return _success(
        {'field': field, 'value': value, 'updated_count': len(rows), 'product_ids': [row['product_id'] for row in rows]},
        source='products', action='batch_update', row_count=len(rows),
        unknowns=[f'商品不存在: {item}' for item in missing],
    )


def _validate_tags_payload(data):
    product_ids = [str(item) for item in (data.get('product_ids') or []) if str(item)]
    tag = str(data.get('tag') or '').strip()
    if not product_ids or not tag:
        return None, None
    return product_ids, tag


@catalog_mutations_bp.route('/api/products/batch-tags', methods=['POST', 'DELETE'])
def mutate_product_tags():
    data = _payload()
    product_ids, tag = _validate_tags_payload(data)
    if not product_ids or not tag:
        return failure('VALIDATION_ERROR', '商品ID列表和标签不能为空', status=422)
    operator, reason = _operator_reason(data, '批量更新商品标签')

    with get_db() as connection:
        placeholders = ','.join('?' for _ in product_ids)
        existing = {
            row['product_id'] for row in connection.execute(
                f'SELECT product_id FROM products WHERE product_id IN ({placeholders})', product_ids
            ).fetchall()
        }
        if request.method == 'POST':
            affected = 0
            for product_id in existing:
                cursor = connection.execute(
                    'INSERT OR IGNORE INTO product_tags (product_id, tag) VALUES (?, ?)',
                    (product_id, tag),
                )
                affected += int(cursor.rowcount > 0)
            action = 'add_tag'
            result_key = 'affected_count'
        else:
            affected = connection.execute(
                f'DELETE FROM product_tags WHERE product_id IN ({placeholders}) AND tag = ?',
                [*product_ids, tag],
            ).rowcount
            action = 'remove_tag'
            result_key = 'deleted_count'
        AuditRepo.record(
            'product_tags', tag, action, operator, reason,
            {'product_ids': sorted(existing), 'tag': tag},
            {'product_ids': sorted(existing), 'tag': tag, result_key: affected},
            connection=connection,
        )
        connection.commit()

    missing = sorted(set(product_ids) - existing)
    return _success(
        {'tag': tag, result_key: affected, 'product_ids': sorted(existing)},
        source='product_tags', action=action, row_count=affected,
        unknowns=[f'商品不存在: {item}' for item in missing],
    )
