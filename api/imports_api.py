from flask import Blueprint, request

from api.api_response import failure, success
from services.import_service import ImportConflictError, ImportValidationError, import_service


imports_bp = Blueprint('imports', __name__)


@imports_bp.route('/api/imports/preview', methods=['POST'])
def preview_import():
    file = request.files.get('file')
    if file is None or not file.filename:
        return failure('VALIDATION_ERROR', '请上传 Excel 文件', status=422)
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return failure('VALIDATION_ERROR', '仅支持 .xlsx 或 .xls 文件', status=422)
    try:
        return success(import_service.preview(file.filename, file.read(), request.args.get('source_type', 'product_day')))
    except ImportValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)


@imports_bp.route('/api/imports', methods=['POST'])
def confirm_import():
    payload = request.get_json(silent=True) or {}
    try:
        result = import_service.confirm(payload.get('preview_id'), payload.get('mapping'))
    except ImportValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
    return success(result, status=201)


@imports_bp.route('/api/imports', methods=['GET'])
def list_imports():
    return success(import_service.list_batches())


@imports_bp.route('/api/imports/<batch_id>/revert', methods=['POST'])
def revert_import(batch_id):
    try:
        return success(import_service.revert(batch_id))
    except ImportConflictError as error:
        return failure('CONFLICT', str(error), status=409)
    except ImportValidationError as error:
        return failure('VALIDATION_ERROR', str(error), status=422)
