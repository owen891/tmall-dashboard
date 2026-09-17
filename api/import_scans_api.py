from flask import Blueprint, request

from api.api_response import failure, json_object, success
from services.import_scan_service import (
    ImportScanConflictError,
    ImportScanService,
    ImportScanValidationError,
)
from services.shop_scope_service import (
    audit_identity,
    current_request_shop_id,
    require_import_scan_capability,
)


import_scans_bp = Blueprint('import_scans', __name__)


def _payload():
    return json_object(request)


def _audit_payload(payload, default_reason):
    data = dict(payload or {})
    operator, reason = audit_identity(data, default_reason)
    data.pop('operator', None)
    data.pop('actor', None)
    data.pop('reason', None)
    return data, operator, reason


def _require(capability):
    denied = require_import_scan_capability(capability)
    if denied is not None:
        return denied
    return None


def _error(error, status=422):
    reason = getattr(error, 'code', 'VALIDATION_ERROR')
    if isinstance(error, ImportScanConflictError):
        status = 409
    elif reason in {'SCAN_JOB_NOT_FOUND', 'SCAN_FILE_NOT_FOUND'}:
        status = 404
    else:
        status = 422
    public_reason = reason if reason.startswith('SCAN_') and reason != 'SCAN_VALIDATION_ERROR' else 'VALIDATION_ERROR'
    return failure(public_reason, str(error), details={'reason': reason}, status=status)


@import_scans_bp.route('/api/import-scans', methods=['GET'])
def list_scan_jobs():
    denied = _require('view')
    if denied is not None:
        return denied
    shop_id = current_request_shop_id()
    return success(
        ImportScanService.list_jobs(shop_id),
        scan_environment=ImportScanService.scan_environment(shop_id),
        evidence=[{'source': 'import_scan_jobs'}],
    )


@import_scans_bp.route('/api/import-scans', methods=['POST'])
def create_scan_job():
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '创建本地扫描任务')
        payload['shop_id'] = current_request_shop_id()
        return success(ImportScanService.create_job(payload, operator=operator, reason=reason), status=201)
    except ImportScanValidationError as error:
        return _error(error)


@import_scans_bp.route('/api/import-scans/<int:job_id>', methods=['PUT'])
def update_scan_job(job_id):
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '更新本地扫描任务')
        return success(ImportScanService.update_job(job_id, payload, operator=operator, reason=reason))
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>', methods=['DELETE'])
def disable_scan_job(job_id):
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '停用本地扫描任务')
        return success(ImportScanService.disable_job(job_id, operator=operator, reason=reason))
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>/delete', methods=['POST'])
def delete_scan_job(job_id):
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '删除本地扫描任务')
        return success(ImportScanService.delete_job(job_id, operator=operator, reason=reason))
    except ImportScanConflictError as error:
        return _error(error, 409)
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>/run', methods=['POST'])
def run_scan_job(job_id):
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '手动运行本地扫描任务')
        return success(ImportScanService.run_job_once(job_id, force=bool(payload.get('force')), operator=operator, reason=reason))
    except ImportScanConflictError as error:
        return _error(error, 409)
    except ImportScanValidationError as error:
        return _error(error)


@import_scans_bp.route('/api/import-scans/<int:job_id>/runs', methods=['GET'])
def list_scan_runs(job_id):
    denied = _require('view')
    if denied is not None:
        return denied
    try:
        return success(ImportScanService.list_runs(job_id), evidence=[{'source': 'import_scan_runs'}])
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>/files', methods=['GET'])
def list_scan_files(job_id):
    denied = _require('view')
    if denied is not None:
        return denied
    try:
        return success(
            ImportScanService.list_files(job_id, request.args.get('status')),
            evidence=[{'source': 'import_scan_files'}],
        )
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>/files/<int:file_id>/retry', methods=['POST'])
def retry_scan_file(job_id, file_id):
    denied = _require('manage')
    if denied is not None:
        return denied
    try:
        payload, operator, reason = _audit_payload(_payload(), '重试本地扫描文件')
        return success(ImportScanService.retry_file(job_id, file_id, operator=operator, reason=reason))
    except ImportScanConflictError as error:
        return _error(error, 409)
    except ImportScanValidationError as error:
        return _error(error, 404)
