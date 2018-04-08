from flask import jsonify, request
from . import api

@api.errorhandler(400)
def bad_request(error):
    return jsonify(
        error='bad request',
        url=request.url
    ), 400

@api.errorhandler(403)
def forbidden(error):
    return jsonify(
        error='forbidden',
        url=request.url
    ), 403

@api.errorhandler(404)
def not_found(error):
    return jsonify(
        error='not found',
        url=request.url
    ), 404
