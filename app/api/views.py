
import json, time
from flask import (Blueprint, jsonify, request, abort, redirect,
                   render_template, send_file, current_app)

from . import api
from app.utils import json_converter, json_loads, format_data
from app.libs.zapi import Zapi


# get app configuration
@api.route('/', methods=['GET'])
def get_status():
    if current_app.debug:
        return jsonify(**format_data(dict(current_app.config)))
    return 'ok'


@api.route('/add_public_ip')
def add_public_ip():
    result = format_data(request.args.to_dict())
    result.update(
        Zapi().add_public_host(**result))
    return jsonify(**result)


@api.route('/sync_by_device_id', methods=['GET'])
def sync_by_device_id():
    result = format_data(request.args.to_dict())
    result.update(
        Zapi().sync_by_device_id(**result))
    if result.get('format') == 'html':
        return render_template('sync_by_device_id.html', result=result)
    return jsonify(**result)


@api.route('/redirect_latest', methods=['GET'])
def redirect_latest():
    return redirect(
        Zapi().get_link_latest(**format_data(request.args.to_dict())))


@api.route('/itemhistory', methods=['POST'])
def itemhistory():
    return jsonify(
        Zapi().get_items_history(**format_data(request.get_json())))


@api.route('/chart', methods=['GET', 'POST'])
def chart():
    return send_file(
        Zapi().get_chart_cached(**format_data(request.args.to_dict())),
        mimetype='image/png')
