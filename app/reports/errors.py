from flask import jsonify, request, render_template
from . import reports

@reports.errorhandler(400)
def bad_request(error):
    return jsonify(
        error='bad request',
        url=request.url
    ), 400

@reports.errorhandler(403)
def forbidden(error):
    return jsonify(
        error='forbidden',
        url=request.url
    ), 403

@reports.errorhandler(404)
def not_found(error):
    return render_template('reports/404.html')
