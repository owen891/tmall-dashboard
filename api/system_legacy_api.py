"""System Legacy API - 系统管理相关接口（旧版）

从 data_api.py 拆分出来的独立模块，现仅保留：
- 操作日志读写（/api/logs）
"""

from flask import Blueprint, jsonify, request

from db import get_db
from api.api_response import failure, json_object


system_legacy_bp = Blueprint('system_legacy', __name__)


@system_legacy_bp.route('/api/logs', methods=['GET'])
def get_logs():
    """获取最近操作日志"""
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()]
    return jsonify(rows)

@system_legacy_bp.route('/api/logs', methods=['POST'])
def create_log():
    """记录操作日志"""
    data = json_object(request)
    action = str(data.get('action') or '').strip()
    detail = str(data.get('detail') or '').strip()
    operator = str(data.get('operator') or 'admin').strip() or 'admin'
    if not action:
        return failure('VALIDATION_ERROR', 'action is required', status=422)
    with get_db() as conn:
        conn.execute(
            'INSERT INTO operation_logs (action, detail, operator) VALUES (?, ?, ?)',
            (action, detail, operator)
        )
        conn.commit()
    return jsonify({'success': True})
