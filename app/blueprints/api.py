import json

from flask import Blueprint, jsonify, request, abort, redirect, render_template, send_file
from time import time

from app import app
from app.utils import json_converter, json_loads
from app.libs import zapi
from app.libs.datapi import dbexecute

api = Blueprint('api', __name__, url_prefix='/api')

# get app configuration
@api.route('/', methods=['GET'])
def get_status():
    if app.debug:
        data = json.dumps(dict(app.config), default=json_converter)
        return jsonify(json.loads(data))
    else:
        return 'ok'

@api.route('/add_public_ip')
def add_public_ip():
    device_ip = request.args.get('ip')
    if not device_ip:
        return jsonify(error='incorrect argument ip', timestamp=timestamp)
    error = ''
    devices = None
    timestamp = int(time.time())
    try:
        zbx = zapi.Zapi()
        zbx_device = zbx.get_public_host(device_ip)
        if len(zbx_device):
            return jsonify(
                devices = zbx_device,
                error = '',
                timestamp = timestamp
            )
        else:
            devices = zbx.add_public_host(device_ip)
    except Exception as err:
        app.logger.error('{0} {1}'.format(device_ip, repr(err)))
        error = repr(e)
    return jsonify(
        devices = devices,
        error = '',
        timestamp = timestamp
    )

@api.route('/sync_by_device_id', methods=['GET'])
def sync_by_device_id():
    device_id = request.args.get('device_id')
    format = request.args.get('format', 'json')
    result = zapi.sync_by_device_id(device_id)
    if format == 'html':
        return render_template('sync_by_device_id.html', result=result)
    return jsonify(result)

@api.route('/redirect_latest', methods=['GET'])
def redirect_latest():
    return redirect(zapi.Zapi().get_link_latest(**request.args.to_dict()))

@api.route('/itemhistory', methods=['GET'])
def itemhistory():
    return jsonify(zapi.Zapi().get_items_history(**{k: json_loads(v) for k, v in request.args.to_dict().items()}))

@api.route('/chart', methods=['GET'])
def chart():
    return send_file(zapi.Zapi().get_chart_cached(**request.args.to_dict()),
                     mimetype='image/png')
