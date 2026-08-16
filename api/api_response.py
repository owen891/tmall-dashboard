from uuid import uuid4

from flask import jsonify


AVAILABILITY_VALUES = {
    'available', 'no-data', 'insufficient-data', 'missing-fields',
    'calculation-failed', 'source-unavailable', 'partial',
}
EVIDENCE_LEVEL_VALUES = {'full', 'partial', 'insufficient'}


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
            freshness=None, evidence=None, assumptions=None, unknowns=None):
    if availability not in AVAILABILITY_VALUES:
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
        'requestId': uuid4().hex,
    }), status


def failure(code, message, details=None, status=400):
    return jsonify({
        'ok': False,
        'code': code,
        'message': message,
        'details': details or {},
        # Error responses carry the same context contract as successful
        # responses so the UI can explain what is blocked without parsing text.
        'availability': 'calculation-failed',
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
