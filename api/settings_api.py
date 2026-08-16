from flask import Blueprint, request

from api.api_response import failure, success
from services.settings_service import SettingsValidationError, settings_service


settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/api/settings', methods=['GET'])
def get_settings():
    return success(
        settings_service.get(),
        evidence_level='full',
        freshness={'source': 'persisted_settings'},
        evidence=[{'source': 'settings', 'row_count': 1}],
    )


@settings_bp.route('/api/settings', methods=['PUT'])
def update_settings():
    payload = request.get_json(silent=True) or {}
    operator = payload.pop('operator', None) or 'admin'
    reason = payload.pop('reason', None) or '更新系统设置'
    try:
        return success(
            settings_service.update(payload, operator, reason),
            evidence_level='full',
            freshness={'source': 'persisted_settings', 'action': 'update'},
            evidence=[{'source': 'settings', 'row_count': 1, 'action': 'update',
                       'operator': operator, 'reason': reason}],
            assumptions=['设置写入只改变口径和模板配置，不改写历史事实'],
        )
    except SettingsValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
