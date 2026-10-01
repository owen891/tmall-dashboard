from uuid import uuid4

from flask import current_app, has_app_context, jsonify
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


AVAILABILITY_VALUES = {
    'available', 'no-data', 'insufficient-data', 'missing-fields',
    'calculation-failed', 'source-unavailable', 'partial',
}
EVIDENCE_LEVEL_VALUES = {'full', 'partial', 'insufficient'}

# Error responses carry an availability so the UI can explain *why* there is
# nothing to show. `failure()` used to hard-code 'calculation-failed' for every
# error, so all 252 call sites reported "计算失败" — including a missing query
# parameter and an empty year. Map the codes whose meaning is unambiguous;
# anything unmapped keeps the historical default so no caller changes behaviour
# by accident.
CODE_AVAILABILITY = {
    'NO_DATA': 'no-data',
    'NOT_FOUND': 'no-data',
    'VALIDATION_ERROR': 'missing-fields',
    'DATA_CAPABILITY_ERROR': 'missing-fields',
    'PAGE_CAPABILITY_ERROR': 'missing-fields',
    'ENVIRONMENT_ERROR': 'source-unavailable',
    'TOOL_NOT_AVAILABLE': 'source-unavailable',
    'QUALITY_GATE_FAILED': 'insufficient-data',
}


def _resolve_availability(availability, code=None):
    """Pick the availability for an error response, warning when it is bogus."""
    if availability is None:
        return CODE_AVAILABILITY.get(code, 'calculation-failed')
    if availability not in AVAILABILITY_VALUES:
        if has_app_context():
            current_app.logger.warning(
                'invalid availability %r for error code %s; falling back to calculation-failed',
                availability, code,
            )
        return 'calculation-failed'
    return availability


class JsonObjectError(ValueError):
    """Raised when a JSON write payload is not an object."""


def json_object(request, *, allow_empty=True):
    """Read a JSON object; distinguish an empty body from malformed JSON."""
    if allow_empty and not request.get_data(cache=True):
        return {}
    try:
        data = request.get_json(silent=False)
    except (BadRequest, UnsupportedMediaType) as error:
        raise JsonObjectError('请求体不是合法 JSON') from error
    if not isinstance(data, dict):
        raise JsonObjectError('请求体必须是 JSON 对象')
    return data


def evidence_level_for(availability, *, missing_inputs=(), missing_ranges=()):
    """Resolve evidence strength without treating an empty result as proven zero."""
    if availability == 'available' and not missing_inputs and not missing_ranges:
        return 'full'
    if availability in {'no-data', 'source-unavailable'}:
        return 'insufficient'
    return 'partial'


def limitations_for(availability, *, missing_inputs=(), missing_ranges=()):
    limitations = []
    if missing_inputs:
        limitations.append(f"缺少必要输入: {', '.join(str(item) for item in missing_inputs)}")
    if missing_ranges:
        limitations.append(f'日期范围存在缺口: {len(missing_ranges)} 段')
    if availability == 'no-data':
        limitations.append('当前筛选范围没有可用记录')
    elif availability == 'source-unavailable':
        limitations.append('数据源不可用')
    return limitations


def success(data, availability='available', status=200, *, capabilities=None,
            filters=None, missing_fields=None, missing_ranges=None, source_batches=None,
            evidence_level='full', missing_inputs=None, limitations=None,
            freshness=None, evidence=None, assumptions=None, unknowns=None,
            scan_environment=None):
    if availability not in AVAILABILITY_VALUES:
        if has_app_context():
            current_app.logger.warning(
                'invalid availability %r passed to success(); falling back to calculation-failed',
                availability,
            )
        availability = 'calculation-failed'
    if evidence_level not in EVIDENCE_LEVEL_VALUES:
        evidence_level = 'insufficient'
    return jsonify({
        'ok': True,
        'data': data,
        'availability': availability,
        'capabilities': dict(capabilities or {}),
        'filters': dict(filters or {}),
        'missing_fields': list(missing_fields or []),
        'missing_ranges': list(missing_ranges or []),
        'source_batches': list(source_batches or []),
        'evidence_level': evidence_level,
        'missing_inputs': list(missing_inputs or []),
        'limitations': list(limitations or []),
        'freshness': dict(freshness or {}),
        'evidence': list(evidence or []),
        'assumptions': list(assumptions or []),
        'unknowns': list(unknowns or []),
        **({'scan_environment': dict(scan_environment)} if scan_environment is not None else {}),
        'requestId': uuid4().hex,
    }), status


def failure(code, message, details=None, status=400, *, availability=None):
    return jsonify({
        'ok': False,
        'code': code,
        'message': message,
        'details': details or {},
        # Error responses carry the same context contract as successful
        # responses so the UI can explain what is blocked without parsing text.
        # `availability` defaults to a per-code mapping (see CODE_AVAILABILITY)
        # rather than a blanket 'calculation-failed'.
        'availability': _resolve_availability(availability, code),
        'capabilities': {},
        'filters': {},
        'missing_fields': [],
        'missing_ranges': [],
        'source_batches': [],
        'evidence_level': 'insufficient',
        'missing_inputs': [],
        'limitations': [message],
        'freshness': {},
        'evidence': [],
        'assumptions': [],
        'unknowns': [],
        'requestId': uuid4().hex,
    }), status
