from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from services.goals_service import GoalConflictError, GoalValidationError, goals_service
from services.shop_scope_service import reject_legacy_shop_scope


goals_bp = Blueprint('goals', __name__)


def _legacy_scope_denied():
    return reject_legacy_shop_scope('经营目标')


@goals_bp.route('/api/goals', methods=['POST'])
def save_goals():
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        result = goals_service.create_or_replace(
            payload.get('year'), payload.get('annual_target'), payload.get('version'),
            payload.get('growth_multiplier'), payload.get('operator') or 'admin',
            payload.get('reason') or '创建或更新年度目标',
        )
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(
        result,
        status=201,
        freshness={'period': str(result.get('year'))},
        evidence=[{
            'source': 'goal_versions', 'year': result.get('year'),
            'version': result.get('version'), 'annual_total': result.get('annual_total'),
        }, {
            'source': 'daily_goals', 'year': result.get('year'),
            'day_count': result.get('day_count', 0),
        }],
        assumptions=['目标写入不会把缺失经营事实当作零值'],
    )


@goals_bp.route('/api/goals/<int:year>/suggestion', methods=['GET'])
def suggest_goals(year):
    if (denied := _legacy_scope_denied()):
        return denied
    try:
        result = goals_service.suggest(year, request.args.get('growth_multiplier', 1.0))
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result)


@goals_bp.route('/api/goals/<int:year>/allocation-preview', methods=['GET'])
def allocation_preview(year):
    if (denied := _legacy_scope_denied()):
        return denied
    try:
        result = goals_service.allocation_preview(year, request.args.get('annual_target'))
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result)


@goals_bp.route('/api/goals/<int:year>', methods=['GET'])
def get_goals(year):
    if (denied := _legacy_scope_denied()):
        return denied
    result = goals_service.get_year(year)
    if result is None:
        return failure('NOT_FOUND', '该年度尚未创建目标', status=404)
    return success(
        result,
        evidence_level='full',
        freshness={'period': str(year)},
        evidence=[{'source': 'goal_versions', 'year': year, 'row_count': 1}],
    )


@goals_bp.route('/api/goals/<int:year>/locks', methods=['POST'])
def lock_goals(year):
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        result = goals_service.lock_period(
            year, payload.get('version'), payload.get('period_type'), payload.get('period_key'),
        )
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(
        result,
        status=201,
        freshness={'period': str(year)},
        evidence=[{'source': 'goal_locks', 'year': year, 'period_type': result.get('period_type'),
                   'period_key': result.get('period_key'), 'version': result.get('version')}],
    )


@goals_bp.route('/api/goals/<int:year>/periods', methods=['GET'])
def goal_periods(year):
    if (denied := _legacy_scope_denied()):
        return denied
    result = goals_service.periods(year)
    if result is None:
        missing_inputs = ['goals']
        return success(
            {'year': year, 'version': None, 'months': [], 'levels': {}, 'actual': {}},
            availability='no-data',
            evidence_level=evidence_level_for('no-data', missing_inputs=missing_inputs),
            missing_inputs=missing_inputs,
            limitations=limitations_for('no-data', missing_inputs=missing_inputs),
            freshness={'period': str(year)},
            evidence=[{'source': 'goal_versions', 'year': year, 'row_count': 0}],
        )
    return success(
        result,
        evidence_level='full',
        freshness={'period': str(year)},
        evidence=[{'source': 'daily_goals', 'year': year, 'row_count': len(result.get('months', []))}],
    )


@goals_bp.route('/api/goals/<int:year>/adjustments', methods=['POST'])
def adjust_goal_period(year):
    if (denied := _legacy_scope_denied()):
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        result = goals_service.adjust_period(
            year, payload.get('version'), payload.get('period_type'), payload.get('period_key'),
            payload.get('target_amount'), payload.get('operator'), payload.get('reason'), payload.get('lock'),
        )
        return success(
            result,
            freshness={'period': str(year)},
            evidence=[{'source': 'goal_adjustments', 'year': year,
                       'period_type': result.get('period_type'), 'period_key': result.get('period_key'),
                       'version': result.get('version')}],
        )
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
