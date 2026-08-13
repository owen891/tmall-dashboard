from flask import Blueprint, jsonify

from repos.system_repo import SystemRepo


status_bp = Blueprint('status', __name__)


@status_bp.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(SystemRepo.get_status())
