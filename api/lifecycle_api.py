from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, json_object, limitations_for, success
from services.category_mode_service import category_filters_from_request
from services.lifecycle_service import LifecycleConflictError, LifecycleValidationError, lifecycle_service
from services.shop_scope_service import reject_legacy_shop_scope


lifecycle_bp = Blueprint('lifecycle_domain', __name__)


@lifecycle_bp.route('/api/lifecycle/assessments')
def assessments():
    if (denied := reject_legacy_shop_scope('生命周期')):
        return denied
    rows = lifecycle_service.list()
    category_filters = category_filters_from_request()
    if category_filters.get('shop_label'):
        from db import get_db
        _label = category_filters['shop_label']
        with get_db() as _conn:
            _ids = [str(r['product_id']) for r in _conn.execute(
                "SELECT product_id FROM products WHERE (shop_label = ? OR instr(',' || shop_label || ',', ',' || ? || ',') > 0)",
                (_label, _label))]
        _idset = set(_ids)
        rows = [row for row in rows if str(row['product_id']) in _idset]
    product_id = request.args.get('productId') or request.args.get('product_id')
    stage = request.args.get('lifecycleStage') or request.args.get('lifecycle_stage')
    if product_id:
        rows = [row for row in rows if row['product_id'] == product_id]
    if stage:
        rows = [row for row in rows if row['stage'] == stage]
    enough_days = bool(rows) and all(row['continuous_valid_days'] >= 60 for row in rows)
    complete_seasonality = bool(rows) and all(row['complete_months'] >= 12 for row in rows)
    if not rows:
        availability = 'no-data'
    elif enough_days:
        availability = 'available'
    else:
        availability = 'insufficient-data'
    missing_inputs = []
    if not rows:
        missing_inputs = ['lifecycle', 'product_monthly']
    elif not enough_days:
        missing_inputs = ['product_daily.date_coverage_60d']
    # 集合级 capabilities 描述的是「整批数据」的状态，用于页面整体提示；
    # 它**不能**代表某一行能否编辑——只要有一行不足 60 天，all() 就会把整页
    # 锁死，而那些数据充足的商品也跟着不能改阶段。行级动作必须按行判定。
    # 逐行能力放进 capabilities.rows（success() 的顶层键是固定白名单，
    # 不能为单个接口加列），前端按 product_id 取用。
    row_capabilities = {
        str(row['product_id']): {
            'can_edit_stage': bool((row.get('continuous_valid_days') or 0) >= 60),
            'can_lock_stage': bool((row.get('continuous_valid_days') or 0) >= 60),
            'can_infer_seasonality': bool((row.get('complete_months') or 0) >= 12),
            'continuous_valid_days': row.get('continuous_valid_days'),
            'complete_months': row.get('complete_months'),
        }
        for row in rows
    }
    return success(
        rows,
        availability=availability,
        capabilities={
            'can_export': bool(rows),
            # 保留集合级语义（整批是否都够）供页面整体提示使用
            'can_edit_stage': enough_days,
            'can_lock_stage': enough_days,
            'can_infer_seasonality': complete_seasonality,
            'rows': row_capabilities,
        },
        filters={key: value for key, value in {
            'product_id': product_id, 'lifecycle_stage': stage,
        }.items() if value},
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'end': max((row.get('data_cutoff_date') or '' for row in rows), default=None)},
        evidence=[{'source': 'lifecycle_profiles', 'row_count': len(rows)}],
    )


@lifecycle_bp.route('/api/lifecycle/<product_id>', methods=['PUT'])
def update_assessment(product_id):
    if (denied := reject_legacy_shop_scope('生命周期')):
        return denied
    payload = json_object(request)
    try:
        result = lifecycle_service.update(product_id, payload)
        enough_days = int(result.get('continuous_valid_days') or 0) >= 60
        availability = 'available' if enough_days else 'insufficient-data'
        missing_inputs = [] if enough_days else ['product_daily.date_coverage_60d']
        return success(
            result,
            availability=availability,
            evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
            missing_inputs=missing_inputs,
            limitations=limitations_for(availability, missing_inputs=missing_inputs),
            freshness={'end': result.get('data_cutoff_date'), 'product_id': product_id},
            evidence=[
                {'source': 'lifecycle_profiles', 'product_id': product_id, 'version': result.get('version')},
                {'source': 'lifecycle_history', 'product_id': product_id, 'action': 'update'},
            ],
            assumptions=['生命周期人工调整不会把不足 60 天的数据包装成算法结论'],
        )
    except LifecycleConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except LifecycleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@lifecycle_bp.route('/api/lifecycle/<product_id>/history')
def history(product_id):
    if (denied := reject_legacy_shop_scope('生命周期')):
        return denied
    from repos.lifecycle_repo import LifecycleRepo
    rows = LifecycleRepo.history(product_id)
    availability = 'available' if rows else 'no-data'
    missing_inputs = [] if rows else ['lifecycle_history']
    return success(
        rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'lifecycle_history', 'product_id': product_id, 'row_count': len(rows)}],
    )
