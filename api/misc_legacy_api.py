"""Misc Legacy API - 杂项接口（旧版）

从 data_api.py 拆分出来的独立模块，现仅保留：
- 商品字段行内编辑（/api/products/<product_id>/field）
"""

from flask import Blueprint, jsonify, request

from db import get_db
from api.api_response import failure, json_object
from repos.audit_repo import AuditRepo


misc_legacy_bp = Blueprint('misc_legacy', __name__)


@misc_legacy_bp.route('/api/products/<product_id>/field', methods=['PUT'])  # 已迁移到 misc_legacy_api.py
def update_product_field(product_id):
    """行内快速编辑商品字段"""
    data = json_object(request)
    field = str(data.get('field') or '').strip()
    value = str(data.get('value') or '').strip()

    # 安全设计：字段白名单防止SQL注入，仅允许以下字段通过f-string拼入SQL
    ALLOWED_FIELDS = ('tier', 'style', 'scene', 'manager', 'remark')
    if field not in ALLOWED_FIELDS:
        return failure('VALIDATION_ERROR', f'不允许修改字段「{field}」', status=422)
    if not product_id:
        return failure('VALIDATION_ERROR', '缺少 product_id', status=422)

    with get_db() as conn:
        # 检查商品是否存在
        row = conn.execute('SELECT product_id FROM products WHERE product_id = ?', (product_id,)).fetchone()
        if not row:
            return failure('NOT_FOUND', '商品不存在', status=404)

        # 获取旧值用于日志
        old_row = conn.execute(f'SELECT {field} FROM products WHERE product_id = ?', (product_id,)).fetchone()
        old_value = old_row[0] if old_row else ''

        # 更新字段
        conn.execute(
            f'UPDATE products SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (value, product_id)
        )
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (f'修改{field}', f'商品 {product_id}: {field}「{old_value}」→「{value}」', 'admin')
        )
        AuditRepo.record(
            'product', product_id, 'update_field', data.get('operator') or 'admin',
            data.get('reason') or f'修改商品{field}', {field: old_value}, {field: value},
            connection=conn,
        )
        conn.commit()

    return jsonify({'success': True, 'field': field, 'value': value})
