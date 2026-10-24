from flask import Blueprint, request

from api.api_response import failure, json_object, success
from db import get_db, get_shop_id
from repos.audit_repo import AuditRepo
from services.shop_scope_service import audit_identity, reject_legacy_shop_scope, require_admin_write
from services.tier_source import MANUAL_TIER_SOURCE, tier_source_for_write

from datetime import datetime


catalog_mutations_bp = Blueprint('catalog_mutations', __name__)

ALLOWED_PRODUCT_FIELDS = {'tier', 'style', 'scene', 'manager', 'remark'}


def _payload():
    return json_object(request)


def _operator_reason(data, default_reason):
    return audit_identity(data, default_reason)


def _starred(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in {0, 1}:
        return value
    if isinstance(value, str) and value.strip() in {'0', '1'}:
        return int(value.strip())
    raise ValueError('starred 必须是布尔值或 0/1')


def _success(data, *, source, action, row_count=1, status=200, unknowns=None):
    return success(
        data,
        status=status,
        availability='available' if row_count else 'no-data',
        evidence_level='full' if row_count else 'insufficient',
        evidence=[{'source': source, 'action': action, 'row_count': row_count}],
        unknowns=list(unknowns or []),
    )


def _legacy_catalog_guard():
    return reject_legacy_shop_scope('商品目录') or require_admin_write()


@catalog_mutations_bp.route('/api/products/<product_id>/metadata', methods=['PUT'])
def update_product_metadata(product_id):
    if (denied := _legacy_catalog_guard()):
        return denied
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
            f'SELECT product_id, {field}, tier_source FROM products WHERE product_id = ?',
            (product_id,),
        ).fetchone()
        if row is None:
            return failure('NOT_FOUND', '商品不存在', status=404)
        before = row[field]
        before_source = row['tier_source']
        next_source = tier_source_for_write(field, before_source)
        connection.execute(
            f'UPDATE products SET {field} = ?, tier_source = ?, '
            'updated_at = CURRENT_TIMESTAMP WHERE product_id = ?',
            (value, next_source, product_id),
        )
        AuditRepo.record(
            'product', product_id, 'update_metadata', operator, reason,
            {field: before, 'tier_source': before_source},
            {field: value, 'tier_source': next_source}, connection=connection,
        )
        connection.commit()

    return _success(
        {'product_id': product_id, 'field': field, 'value': value,
         'tier_source': MANUAL_TIER_SOURCE if field == 'tier' else before_source},
        source='products', action='update_metadata',
    )


@catalog_mutations_bp.route('/api/products/<product_id>/star', methods=['POST'])
def set_product_star(product_id):
    if (denied := _legacy_catalog_guard()):
        return denied
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
            try:
                starred = _starred(data.get('starred'))
            except ValueError as error:
                return failure('VALIDATION_ERROR', str(error), status=422)
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
    if (denied := _legacy_catalog_guard()):
        return denied
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
            f'SELECT product_id, {field}, tier_source FROM products WHERE product_id IN ({placeholders})',
            product_ids,
        ).fetchall()
        # 改 tier 才把来源改成 manual；改 style 必须保留每行自己的来源，
        # 否则一次批量改风格会把全部分层来源抹平，算法之后就再也改不动它们。
        for row in rows:
            next_source = tier_source_for_write(field, row['tier_source'])
            AuditRepo.record(
                'product', row['product_id'], 'batch_update', operator, reason,
                {field: row[field], 'tier_source': row['tier_source']},
                {field: value, 'tier_source': next_source}, connection=connection,
            )
        if rows:
            if field == 'tier':
                connection.execute(
                    f'UPDATE products SET tier = ?, tier_source = ?, '
                    f'updated_at = CURRENT_TIMESTAMP WHERE product_id IN ({placeholders})',
                    [value, MANUAL_TIER_SOURCE, *product_ids],
                )
            else:
                connection.execute(
                    f'UPDATE products SET {field} = ?, '
                    f'updated_at = CURRENT_TIMESTAMP WHERE product_id IN ({placeholders})',
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
    if (denied := _legacy_catalog_guard()):
        return denied
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


# ===== 商品目标（product_targets，2026-10-24 商品列表参考 BI 重构补全）=====
# period 支持 'YYYY-MM'（月目标）或 'YYYY-MM-DD'（日目标）；达成值按同窗口从
# daily_data 聚合（先聚合再相比），店铺维度沿用请求作用域。

def _normalize_target_period(value):
    period = str(value or '').strip()
    for fmt in ('%Y-%m-%d', '%Y-%m'):
        try:
            return datetime.strptime(period, fmt).strftime(fmt.replace('%Y', '%Y').replace('%m', '%m').replace('%d', '%d')), fmt
        except (TypeError, ValueError):
            continue
    raise ValueError('period 必须是 YYYY-MM 或 YYYY-MM-DD')


def _target_period_window(period, fmt):
    if fmt == '%Y-%m':
        start = datetime.strptime(period, '%Y-%m')
        next_month = datetime(start.year + (start.month // 12), (start.month % 12) + 1, 1)
        return start.strftime('%Y-%m-%d'), next_month.strftime('%Y-%m-%d')
    return period, period


def _target_number(value, field, allow_none=True):
    if value is None or (isinstance(value, str) and not value.strip()):
        if allow_none:
            return None
        raise ValueError(f'{field} 不能为空')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} 必须是数字')
    if not (math_isfinite(number) and number >= 0):
        raise ValueError(f'{field} 必须 >= 0')
    return number


def math_isfinite(number):
    return number == number and number not in (float('inf'), float('-inf'))


def _target_period_end(period, fmt):
    """月度窗口的结束日取当月最后一天（含端点），日目标即当天。"""
    if fmt != '%Y-%m':
        return period
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    from datetime import timedelta
    return (next_month - timedelta(days=1)).strftime('%Y-%m-%d')


@catalog_mutations_bp.route('/api/products/<product_id>/targets', methods=['GET'])
def list_product_targets(product_id):
    with get_db() as connection:
        exists = connection.execute(
            'SELECT 1 FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if exists is None:
            return failure('NOT_FOUND', '商品不存在', status=404)
        shop_id = get_shop_id()
        rows = [dict(row) for row in connection.execute(
            'SELECT id, product_id, tier, period, target_gsv, target_ad_spend, target_ad_ratio, remark, created_at '
            'FROM product_targets WHERE product_id = ? ORDER BY period DESC, id DESC',
            (product_id,),
        ).fetchall()]
        for row in rows:
            try:
                _, fmt = _normalize_target_period(row['period'])
                start, end = _target_period_end(row['period'], fmt), None
                # 月度窗口：start=月初，end=月末；日目标 start=end=当天
                start, end = _target_period_window(row['period'], fmt)
                end = _target_period_end(row['period'], fmt)
                fact = connection.execute(
                    'SELECT COALESCE(SUM(payment_amount), 0) AS gsv, COALESCE(SUM(ad_spend), 0) AS ad_spend, '
                    'COALESCE(SUM(net_sales), 0) AS net_sales '
                    'FROM daily_data WHERE shop_id = ? AND product_id = ? AND date BETWEEN ? AND ?',
                    (shop_id, product_id, start, end),
                ).fetchone()
                achieved_gsv = float(fact['gsv']) if fact else None
                achieved_ad = float(fact['ad_spend']) if fact else None
                achieved_net = float(fact['net_sales']) if fact else None
                row['achieved_gsv'] = achieved_gsv
                row['achieved_expense_ratio'] = (achieved_ad / achieved_net) if (achieved_ad is not None and achieved_net and achieved_net > 0) else None
                row['achievement_rate'] = (achieved_gsv / float(row['target_gsv'])) if (achieved_gsv is not None and row['target_gsv'] and float(row['target_gsv']) > 0) else None
            except ValueError:
                row['achieved_gsv'] = None
                row['achievement_rate'] = None
    return _success(rows, source='product_targets', action='list', row_count=len(rows))


@catalog_mutations_bp.route('/api/products/<product_id>/target', methods=['PUT'])
def upsert_product_target(product_id):
    if (denied := _legacy_catalog_guard()):
        return denied
    data = _payload()
    operator, reason = _operator_reason(data, '设置商品目标')
    try:
        period, fmt = _normalize_target_period(data.get('period'))
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    try:
        target_gsv = _target_number(data.get('target_gsv'), 'target_gsv')
        target_ad_spend = _target_number(data.get('target_ad_spend'), 'target_ad_spend')
        target_ad_ratio = _target_number(data.get('target_ad_ratio'), 'target_ad_ratio')
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    if target_gsv is None and target_ad_spend is None and target_ad_ratio is None:
        return failure('VALIDATION_ERROR', '至少设置一个目标值（销售额/推广花费/费比）', status=422)
    remark = str(data.get('remark') or '').strip() or None

    with get_db() as connection:
        exists = connection.execute(
            'SELECT 1 FROM products WHERE product_id = ?', (product_id,)
        ).fetchone()
        if exists is None:
            return failure('NOT_FOUND', '商品不存在', status=404)
        current = connection.execute(
            'SELECT id, target_gsv, target_ad_spend, target_ad_ratio FROM product_targets '
            'WHERE product_id = ? AND period = ?',
            (product_id, period),
        ).fetchone()
        if current:
            connection.execute(
                'UPDATE product_targets SET target_gsv = ?, target_ad_spend = ?, target_ad_ratio = ?, remark = ? WHERE id = ?',
                (target_gsv, target_ad_spend, target_ad_ratio, remark, current['id']),
            )
            target_id = current['id']
            before = {'target_gsv': current['target_gsv'], 'target_ad_spend': current['target_ad_spend'], 'target_ad_ratio': current['target_ad_ratio']}
        else:
            cursor = connection.execute(
                'INSERT INTO product_targets (product_id, period, target_gsv, target_ad_spend, target_ad_ratio, remark) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (product_id, period, target_gsv, target_ad_spend, target_ad_ratio, remark),
            )
            target_id = cursor.lastrowid
            before = None
        AuditRepo.record(
            'product_target', target_id, 'update' if current else 'create', operator, reason,
            before, {'period': period, 'target_gsv': target_gsv, 'target_ad_spend': target_ad_spend, 'target_ad_ratio': target_ad_ratio},
            connection=connection,
        )
        connection.commit()
    return _success(
        {'product_id': product_id, 'id': target_id, 'period': period,
         'target_gsv': target_gsv, 'target_ad_spend': target_ad_spend, 'target_ad_ratio': target_ad_ratio},
        source='product_targets', action='upsert',
    )


@catalog_mutations_bp.route('/api/products/<product_id>/target', methods=['DELETE'])
def delete_product_target(product_id):
    if (denied := _legacy_catalog_guard()):
        return denied
    data = _payload()
    operator, reason = _operator_reason(data, '清除商品目标')
    try:
        period, _ = _normalize_target_period(data.get('period') or request.args.get('period'))
    except ValueError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    with get_db() as connection:
        row = connection.execute(
            'SELECT id, target_gsv, target_ad_spend, target_ad_ratio FROM product_targets '
            'WHERE product_id = ? AND period = ?',
            (product_id, period),
        ).fetchone()
        if row is None:
            return failure('NOT_FOUND', '该周期没有商品目标', status=404)
        connection.execute('DELETE FROM product_targets WHERE id = ?', (row['id'],))
        AuditRepo.record(
            'product_target', row['id'], 'delete', operator, reason,
            {'period': period, 'target_gsv': row['target_gsv'], 'target_ad_spend': row['target_ad_spend'], 'target_ad_ratio': row['target_ad_ratio']},
            None, connection=connection,
        )
        connection.commit()
    return _success({'product_id': product_id, 'period': period, 'deleted': True}, source='product_targets', action='delete')

