import json

from flask import Blueprint, request

from api.api_response import evidence_level_for, failure, limitations_for, success
from db import get_shop_id
from services.import_service import ImportConflictError, ImportScopeError, ImportValidationError, import_service


imports_bp = Blueprint('imports', __name__)
SUPPORTED_IMPORT_SUFFIXES = ('.xlsx', '.xls', '.csv', '.zip')


@imports_bp.route('/api/imports/preview', methods=['POST'])
def preview_import():
    file = request.files.get('file')
    if file is None or not file.filename:
        return failure('VALIDATION_ERROR', '请选择要预览的表格文件', status=422)
    if not file.filename.lower().endswith(SUPPORTED_IMPORT_SUFFIXES):
        return failure('VALIDATION_ERROR', '仅支持 .xlsx、.xls、.csv 或 .zip 文件', status=422)
    try:
        raw_template = request.form.get('mapping_template')
        mapping_template = json.loads(raw_template) if raw_template else None
        if mapping_template is not None and not isinstance(mapping_template, dict):
            raise ImportValidationError('mapping_template must be an object')
        result = import_service.preview(file.filename, file.read(), request.args.get('source_type', 'product_day'), mapping_template)
        missing = result.get('required_unmapped', [])
        invalid_rows = int(result.get('invalid_rows') or 0)
        invalid_field_count = int(result.get('invalid_field_count') or 0)
        duplicate_keys = int(result.get('duplicate_keys') or 0)
        availability = (
            'missing-fields' if missing
            else 'partial' if invalid_rows or duplicate_keys or invalid_field_count
            else 'available'
        )
        quality_limitations = []
        if invalid_rows:
            quality_limitations.append(f'存在 {invalid_rows} 行质量异常，确认导入前必须修复')
        if duplicate_keys:
            quality_limitations.append(f'存在 {duplicate_keys} 个重复业务键，确认导入前必须去重')
        if invalid_field_count:
            quality_limitations.append(f'存在 {invalid_field_count} 个字段级告警；异常字段已隔离，其他有效字段可继续导入')
        return success(
            result,
            availability=availability,
            evidence_level=evidence_level_for(availability, missing_inputs=missing),
            missing_fields=missing,
            missing_inputs=missing,
            limitations=limitations_for(availability, missing_inputs=missing) + quality_limitations,
            freshness=result.get('date_range') or {},
            evidence=[{
                'source': 'import_preview', 'preview_id': result.get('id'),
                'source_filename': result.get('source_filename'),
                'source_type': result.get('source_type'),
                'source_hash': result.get('source_hash'),
                'row_count': result.get('total_rows', 0),
                'valid_rows': result.get('valid_rows', 0),
            }],
            assumptions=['预览只读取文件，不写入业务事实'],
            unknowns=['确认导入前不会锁定批次版本'] if availability != 'available' else [],
        )
    except ImportScopeError as error:
        return failure('UNSUPPORTED_SCOPE', str(error), status=422)
    except (ImportValidationError, json.JSONDecodeError) as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@imports_bp.route('/api/imports', methods=['POST'])
def confirm_import():
    payload = request.get_json(silent=True) or {}
    try:
        result = import_service.confirm(payload.get('preview_id'), payload.get('mapping'))
    except ImportScopeError as error:
        return failure('UNSUPPORTED_SCOPE', str(error), status=422)
    except ImportValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(
        result,
        status=201,
        evidence_level='full',
        freshness={**(result.get('date_range') or {}), 'latest_update': result.get('completed_at')},
        source_batches=[{'id': result.get('id'), 'source_type': result.get('source_type'),
                         'source_filename': result.get('source_filename'),
                         'completed_at': result.get('completed_at')}],
        evidence=[{
            'source': 'import_batches', 'batch_id': result.get('id'),
            'inserted_count': result.get('inserted_count', 0),
            'updated_count': result.get('updated_count', 0),
            'quality_conclusion': result.get('quality_conclusion'),
            'excluded_summary_rows': result.get('excluded_summary_rows', 0),
            'source_resolution': result.get('source_resolution', {}),
        }],
    )


@imports_bp.route('/api/imports', methods=['GET'])
def list_imports():
    batches = import_service.list_batches()
    availability = 'available' if batches else 'no-data'
    missing_inputs = [] if batches else ['imports']
    latest = max((item.get('completed_at') or item.get('created_at') or '' for item in batches), default=None)
    return success(
        batches,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        freshness={'latest_update': latest},
        evidence=[{'source': 'import_batches', 'row_count': len(batches)}],
    )


@imports_bp.route('/api/imports/<batch_id>/revert', methods=['POST'])
def revert_import(batch_id):
    try:
        result = import_service.revert(batch_id)
        return success(
            result,
            source_batches=[{'id': batch_id}],
            evidence=[{
                'source': 'import_batch_changes', 'batch_id': batch_id,
                'restored_count': result.get('restored_count', 0),
                'skipped_count': result.get('skipped_count', 0),
            }],
            unknowns=['存在未恢复记录，后续批次覆盖关系未改变'] if result.get('skipped_count') else [],
        )
    except ImportScopeError as error:
        return failure('UNSUPPORTED_SCOPE', str(error), status=422)
    except ImportConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except ImportValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@imports_bp.route('/api/imports/<batch_id>/audit', methods=['GET'])
def audit_import(batch_id):
    from db import get_db
    shop_id = get_shop_id()
    with get_db() as connection:
        batch = connection.execute(
            'SELECT id, shop_id FROM import_batches WHERE id = ?', (batch_id,)
        ).fetchone()
        if not batch:
            return failure('VALIDATION_ERROR', '导入批次不存在', status=404)
        if str(batch['shop_id'] or 'default') != shop_id:
            return failure('UNSUPPORTED_SCOPE', '导入批次不属于当前店铺', status=422)
        rows = connection.execute(
            '''SELECT id, table_name, business_key, previous_row, written_by, created_at
               FROM import_batch_changes WHERE batch_id = ? ORDER BY id''',
            (batch_id,),
        ).fetchall()
    audit_rows = [dict(row) for row in rows]
    availability = 'available' if audit_rows else 'no-data'
    missing_inputs = [] if audit_rows else ['import_batch_changes']
    return success(
        audit_rows,
        availability=availability,
        evidence_level=evidence_level_for(availability, missing_inputs=missing_inputs),
        missing_inputs=missing_inputs,
        limitations=limitations_for(availability, missing_inputs=missing_inputs),
        evidence=[{'source': 'import_batch_changes', 'batch_id': batch_id, 'row_count': len(audit_rows)}],
    )
