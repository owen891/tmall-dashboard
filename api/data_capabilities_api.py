from flask import Blueprint, request

from api.api_response import failure, success
from services.data_capability_service import AVAILABILITIES, DOMAIN_DEFINITIONS, build_catalog


data_capabilities_bp = Blueprint('data_capabilities', __name__)


@data_capabilities_bp.route('/api/data-capabilities', methods=['GET'])
def get_data_capabilities():
    domain = request.args.get('domain') or None
    availability = request.args.get('availability') or None
    if domain is not None and domain not in DOMAIN_DEFINITIONS:
        return failure(
            'VALIDATION_ERROR',
            'unknown domain filter',
            {'domain': domain, 'accepted': list(DOMAIN_DEFINITIONS)},
            status=422,
        )
    if availability is not None and availability not in AVAILABILITIES:
        return failure(
            'VALIDATION_ERROR',
            'unknown availability filter',
            {'availability': availability, 'accepted': list(AVAILABILITIES)},
            status=422,
        )

    try:
        data = build_catalog(domain=domain, availability=availability)
    except Exception as error:
        return failure('DATA_CAPABILITY_ERROR', str(error), status=500)

    missing_fields = sorted({
        field['key']
        for item in data['domains']
        for field in item['raw_fields']
        if field['availability'] == 'missing-fields'
    })
    source_batches = sorted({
        batch
        for item in data['domains']
        for batch in item['source_batches']
    })
    domain_items = data['domains']
    if not domain_items or all(
        item['availability'] in {'no-data', 'source-unavailable'}
        for item in domain_items
    ):
        evidence_level = 'insufficient'
    elif any(
        item['availability'] in {'partial', 'missing-fields', 'insufficient-data'}
        for item in domain_items
    ):
        evidence_level = 'partial'
    else:
        evidence_level = 'full'
    limitations = [
        limitation
        for item in domain_items
        for limitation in item.get('limitations', [])
    ]
    limitations.extend(
        f"{item['label']}暂无可用数据"
        for item in domain_items
        if item['availability'] in {'no-data', 'source-unavailable'}
    )
    latest_dates = [
        item['coverage']['end']
        for item in domain_items
        if item.get('coverage', {}).get('end')
    ]
    latest_updates = [
        item['coverage']['latest_update']
        for item in domain_items
        if item.get('coverage', {}).get('latest_update')
    ]
    evidence = [
        {
            'domain': item['key'],
            'availability': item['availability'],
            'row_count': item['coverage']['row_count'],
            'start': item['coverage']['start'],
            'end': item['coverage']['end'],
            'source_batches': item['source_batches'],
        }
        for item in domain_items
    ]
    can_design_pages = any(
        item['availability'] in {'available', 'partial'}
        for item in data['domains']
    )
    return success(
        data,
        availability='available' if data['domains'] else 'no-data',
        capabilities={
            'can_export': bool(data['domains']),
            'can_view_schema': True,
            'can_edit_catalog': False,
            'can_design_pages': can_design_pages,
        },
        filters={key: value for key, value in (
            ('domain', domain), ('availability', availability)
        ) if value is not None},
        missing_fields=missing_fields,
        source_batches=source_batches,
        evidence_level=evidence_level,
        missing_inputs=missing_fields,
        limitations=sorted(set(limitations)),
        freshness={
            'latest_date': max(latest_dates) if latest_dates else None,
            'latest_update': max(latest_updates) if latest_updates else None,
        },
        evidence=evidence,
    )
