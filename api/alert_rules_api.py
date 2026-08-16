from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from services.alert_rules_service import (
    AlertRuleNotFoundError,
    AlertRuleValidationError,
    alert_rules_service,
)


alert_rules_bp = Blueprint('alert_rules_domain', __name__)


@alert_rules_bp.route('/api/alert-rules', methods=['GET'])
def list_alert_rules():
    try:
        rules = alert_rules_service.list(request.args.get('scope'))
        availability = 'available' if rules else 'no-data'
        missing = [] if rules else ['alert_rules']
        return success(
            rules,
            availability=availability,
            evidence_level=evidence_level_for(availability, missing_inputs=missing),
            missing_inputs=missing,
            limitations=limitations_for(availability, missing_inputs=missing),
            evidence=[{'source': 'alert_rules', 'scope': request.args.get('scope'), 'row_count': len(rules)}],
        )
    except AlertRuleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@alert_rules_bp.route('/api/alert-rules', methods=['POST'])
def create_alert_rule():
    try:
        result = alert_rules_service.create(request.get_json(silent=True) or {})
        return success(result, status=201, evidence_level='full',
                       evidence=[{'source': 'alert_rules', 'rule_id': result.get('id'), 'action': 'create'}])
    except AlertRuleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@alert_rules_bp.route('/api/alert-rules/<int:rule_id>', methods=['PUT'])
def update_alert_rule(rule_id):
    try:
        result = alert_rules_service.update(rule_id, request.get_json(silent=True) or {})
        return success(result, evidence_level='full',
                       evidence=[{'source': 'alert_rules', 'rule_id': rule_id, 'action': 'update'}])
    except AlertRuleValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    except AlertRuleNotFoundError as error:
        return failure('NOT_FOUND', str(error), status=404)


@alert_rules_bp.route('/api/alert-rules/<int:rule_id>', methods=['DELETE'])
def delete_alert_rule(rule_id):
    try:
        payload = request.get_json(silent=True) or {}
        alert_rules_service.delete(
            rule_id,
            payload.get('actor') or payload.get('operator') or 'admin',
            payload.get('reason') or '删除预警规则',
        )
        return success({'deleted': True, 'id': rule_id}, evidence_level='full',
                       evidence=[{'source': 'alert_rules', 'rule_id': rule_id, 'action': 'delete'}])
    except AlertRuleNotFoundError as error:
        return failure('NOT_FOUND', str(error), status=404)
