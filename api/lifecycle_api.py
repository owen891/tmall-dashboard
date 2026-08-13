from flask import Blueprint, request

from api.api_response import failure, success
from services.lifecycle_service import LifecycleConflictError, LifecycleValidationError, lifecycle_service


lifecycle_bp = Blueprint('lifecycle_domain', __name__)


@lifecycle_bp.route('/api/lifecycle/assessments')
def assessments():
    return success(lifecycle_service.list())


@lifecycle_bp.route('/api/lifecycle/<product_id>', methods=['PUT'])
def update_assessment(product_id):
    try:
        return success(lifecycle_service.update(product_id, request.get_json(silent=True) or {}))
    except LifecycleConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except LifecycleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@lifecycle_bp.route('/api/lifecycle/<product_id>/history')
def history(product_id):
    from repos.lifecycle_repo import LifecycleRepo
    return success(LifecycleRepo.history(product_id))
