from flask import Blueprint, jsonify, request
import logging
import os

from repos.system_repo import SystemRepo


status_bp = Blueprint('status', __name__)

_frontend_error_logger = logging.getLogger('frontend.errors')


@status_bp.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(SystemRepo.get_status())


@status_bp.route('/api/frontend-errors', methods=['POST'])
def report_frontend_errors():
    """接收前端 JS 错误，写入日志文件"""
    try:
        data = request.get_json(silent=True) or {}
        errors = data.get('errors', [])
        url = data.get('url', '')
        user_agent = data.get('userAgent', '')

        if not errors:
            return jsonify({'status': 'ok', 'received': 0})

        for err in errors:
            _frontend_error_logger.warning(
                'FE_ERROR type=%s msg=%s source=%s line=%s col=%s url=%s ua=%s stack=%s',
                err.get('type', ''),
                err.get('message', '')[:200],
                err.get('source', ''),
                err.get('lineno', 0),
                err.get('colno', 0),
                url,
                user_agent[:100],
                err.get('stack', '')[:500],
            )

        return jsonify({'status': 'ok', 'received': len(errors)})
    except Exception as e:
        _frontend_error_logger.error('frontend error report failed: %s', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500
