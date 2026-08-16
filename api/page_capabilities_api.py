from flask import Blueprint, current_app, request

from api.api_response import failure, success
from services.page_capability_service import build_page_catalog


page_capabilities_bp = Blueprint('page_capabilities', __name__)


@page_capabilities_bp.route('/api/page-capabilities', methods=['GET'])
def get_page_capabilities():
    filters = {
        key: request.args.get(key) or None
        for key in ('page', 'domain', 'support_level', 'modal_kind')
    }
    try:
        data = build_page_catalog(app=current_app, **filters)
    except ValueError as error:
        field, _, value = str(error).replace('unknown ', '').partition(': ')
        return failure(
            'VALIDATION_ERROR',
            'unknown page capability filter',
            {'field': field, 'value': value},
            status=422,
        )
    except Exception as error:
        return failure('PAGE_CAPABILITY_ERROR', str(error), status=500)

    resolved = [
        capability
        for page in data['pages']
        for capability in page['capabilities']
    ]
    if not resolved:
        evidence_level = 'insufficient'
    elif any(item['availability'] == 'no-data' for item in resolved):
        evidence_level = 'insufficient'
    elif any(item['availability'] != 'available' for item in resolved):
        evidence_level = 'partial'
    else:
        evidence_level = 'full'
    limitations = sorted({
        prerequisite
        for item in resolved
        for prerequisite in item['missing_prerequisites']
    })
    return success(
        data,
        availability='available' if data['summary']['can_release'] else 'partial',
        capabilities={
            'can_view_registry': True,
            'can_export': True,
            'can_edit_registry': False,
            'can_release': data['summary']['can_release'],
        },
        filters={key: value for key, value in filters.items() if value is not None},
        evidence_level=evidence_level,
        missing_inputs=sorted({
            domain
            for item in resolved
            for domain in item['missing_domains']
        }),
        limitations=limitations,
        evidence=[
            {
                'page': page['key'],
                'capability_count': len(page['capabilities']),
            }
            for page in data['pages']
        ],
    )
