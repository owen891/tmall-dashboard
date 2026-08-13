from flask import Blueprint, request

from api.api_response import failure, success
from services.goals_service import GoalConflictError, GoalValidationError, goals_service


goals_bp = Blueprint('goals', __name__)


@goals_bp.route('/api/goals', methods=['POST'])
def save_goals():
    payload = request.get_json(silent=True) or {}
    try:
        result = goals_service.create_or_replace(
            payload.get('year'), payload.get('annual_target'), payload.get('version'),
        )
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result, status=201)


@goals_bp.route('/api/goals/<int:year>', methods=['GET'])
def get_goals(year):
    result = goals_service.get_year(year)
    if result is None:
        return failure('NOT_FOUND', '该年度尚未创建目标', status=404)
    return success(result)


@goals_bp.route('/api/goals/<int:year>/locks', methods=['POST'])
def lock_goals(year):
    payload = request.get_json(silent=True) or {}
    try:
        result = goals_service.lock_period(
            year, payload.get('version'), payload.get('period_type'), payload.get('period_key'),
        )
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result, status=201)


@goals_bp.route('/api/goals/<int:year>/periods', methods=['GET'])
def goal_periods(year):
    result = goals_service.periods(year)
    if result is None:
        return success({'year': year, 'version': None, 'months': [], 'levels': {}, 'actual': {}}, availability='no-data')
    return success(result)


@goals_bp.route('/api/goals/<int:year>/adjustments', methods=['POST'])
def adjust_goal_period(year):
    payload = request.get_json(silent=True) or {}
    try:
        return success(goals_service.adjust_period(
            year, payload.get('version'), payload.get('period_type'), payload.get('period_key'),
            payload.get('target_amount'), payload.get('operator'), payload.get('reason'), payload.get('lock'),
        ))
    except GoalConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except (GoalValidationError, TypeError, ValueError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
