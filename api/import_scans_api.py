from flask import Blueprint, request

from api.api_response import failure, success
from services.import_scan_service import (
    ImportScanConflictError,
    ImportScanService,
    ImportScanValidationError,
)


import_scans_bp = Blueprint('import_scans', __name__)


def _error(error, status=422):
    return failure('VALIDATION_ERROR', str(error), status=status)


@import_scans_bp.route('/api/import-scans', methods=['GET'])
def list_scan_jobs():
    return success(ImportScanService.list_jobs(), evidence=[{'source': 'import_scan_jobs'}])


@import_scans_bp.route('/api/import-scans', methods=['POST'])
def create_scan_job():
    try:
        return success(ImportScanService.create_job(request.get_json(silent=True) or {}), status=201)
    except ImportScanValidationError as error:
        return _error(error)


@import_scans_bp.route('/api/import-scans/<int:job_id>', methods=['PUT'])
def update_scan_job(job_id):
    try:
        return success(ImportScanService.update_job(job_id, request.get_json(silent=True) or {}))
    except ImportScanValidationError as error:
        return _error(error)


@import_scans_bp.route('/api/import-scans/<int:job_id>', methods=['DELETE'])
def disable_scan_job(job_id):
    try:
        return success(ImportScanService.disable_job(job_id))
    except ImportScanValidationError as error:
        return _error(error, 404)


@import_scans_bp.route('/api/import-scans/<int:job_id>/run', methods=['POST'])
def run_scan_job(job_id):
    try:
        return success(ImportScanService.run_job_once(job_id))
    except ImportScanConflictError as error:
        return _error(error, 409)
    except ImportScanValidationError as error:
        return _error(error, 422)


@import_scans_bp.route('/api/import-scans/<int:job_id>/runs', methods=['GET'])
def list_scan_runs(job_id):
    return success(ImportScanService.list_runs(job_id), evidence=[{'source': 'import_scan_runs'}])


@import_scans_bp.route('/api/import-scans/<int:job_id>/files', methods=['GET'])
def list_scan_files(job_id):
    return success(
        ImportScanService.list_files(job_id, request.args.get('status')),
        evidence=[{'source': 'import_scan_files'}],
    )
