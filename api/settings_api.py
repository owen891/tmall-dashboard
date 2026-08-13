from flask import Blueprint, request

from api.api_response import failure, success
from services.settings_service import SettingsValidationError, settings_service


settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/api/settings', methods=['GET'])
def get_settings():
    return success(settings_service.get())


@settings_bp.route('/api/settings', methods=['PUT'])
def update_settings():
    try:
        return success(settings_service.update(request.get_json(silent=True) or {}))
    except SettingsValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
