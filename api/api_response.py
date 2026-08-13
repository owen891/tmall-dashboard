from uuid import uuid4

from flask import jsonify


def success(data, availability='available', status=200):
    return jsonify({
        'ok': True,
        'data': data,
        'availability': availability,
        'requestId': uuid4().hex,
    }), status


def failure(code, message, details=None, status=400):
    return jsonify({
        'ok': False,
        'code': code,
        'message': message,
        'details': details or {},
        'requestId': uuid4().hex,
    }), status
