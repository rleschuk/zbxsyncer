import json

from flask import Blueprint, jsonify, request, abort, redirect
from time import time

from app import app
from app.utils import json_converter, json_loads
from app.libs.zapi import Zapi, ZapiAttrException
from app.libs.datapi import dbexecute

api = Blueprint('api', __name__, url_prefix='/api')

# get app configuration
@api.route('/', methods=['GET'])
def get_status():
    data = json.dumps(dict(app.config), default=json_converter)
    return jsonify(json.loads(data))

@api.route('/add_public_ip')
def add_public_ip():
    error = ''
    devices = None
    timestamp = int(time.time())
    if not request.args.get('ip'):
        return jsonify(error='incorrect argument ip',timestamp=timestamp)
    try:
        zbx = Zapi()
        zbx_device = zbx.get_public_host(request.args.get('ip'))
        if len(zbx_device):
            return jsonify(
                devices=zbx_device,
                error='',
                timestamp=timestamp
            )
        else:
            devices = zbx.add_public_host(request.args.get('ip'))
    except Exception as err:
        app.logger.error('{0} {1}'.format(request.args.get('ip'), repr(e)))
        error = repr(e)
    return jsonify(
        devices=devices,
        error='',
        timestamp=timestamp
    )

@api.route('/sync_by_device_id', methods=['GET'])
def sync_by_device_id():
    timestamp = int(time())
    device_id = request.args.get('device_id')
    if not device_id or not device_id.isdigit():
        return jsonify(error='incorrect argument device_id', timestamp=timestamp)

    error = ''
    eqm_device = None
    zbx_device = None
    params = []

    try:
        eqm_device = dbexecute(
            app.config['SQL_SELECT_DEVICES'].format('and d.device_id = %s' % device_id)
        )
        if eqm_device.empty:
            eqm_device = None
        else:
            eqm_device = eqm_device.to_dict(orient='records')[0]
            #try:
            #    Publisher().check_process(eqm_device, timestamp)
            #except Exception as e:
            #    app.logger.error(repr(e))
            zbx = Zapi()
            zbx_device = zbx.get_host(eqm_device)
            if len(zbx_device): zbx_device = zbx_device[0]
            else: zbx_device = None
            params = zbx.sync_host(eqm_device, zbx_device)
    except Exception as err:
        app.logger.error('%s %s' % (device_id, repr(err)))
        error = repr(err)
    return jsonify(
        eqm_device = eqm_device,
        zbx_device = zbx_device,
        error = error,
        params = params,
        timestamp = timestamp
    )

@api.route('/redirect_latest', methods=['GET'])
def redirect_latest():
    if request.args.get('id'):
        return redirect(Zapi().get_link_latest(host=request.args.get('id')))
    elif request.args.get('ip'):
        return redirect(Zapi().get_link_latest(ip=request.args.get('ip')))
    else:
        abort(400)
