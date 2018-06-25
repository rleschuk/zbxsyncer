from flask import Blueprint, jsonify, request, abort, redirect, flash, render_template, current_app
from datetime import datetime, timedelta

from . import reports
from .query import QUERY
from ..libs.datapi import dbexecute


@reports.context_processor
def inject_datetime(): return dict(datetime=datetime, timedelta=timedelta)


@reports.route('/bs_load', methods=['GET'])
def bs_load():
    for f in current_app.config['FLASHES']: flash(*f)
    return render_template('bs_load.html')


@reports.route('/rrl_load', methods=['GET'])
def rrl_load():
    for f in current_app.config['FLASHES']: flash(*f)
    return render_template('rrl_load.html')


@reports.route('/get_devices/<key>', methods=['GET'])
def get_devices(key):
    try: query = QUERY[key].format(**request.args.to_dict())
    except Exception: return abort(400)
    df = dbexecute(query, current_app).fillna('')
    return jsonify(get_devices=df.to_dict(orient='records'))


"""
def load_groups():
    query = '''
        SELECT
            f.rec_id AS device_group_id,
            NULL AS par_group_id,
            266 AS group_type_id,
            f.enf_region_name AS group_name,
            0 AS reg,
            f.rec_id AS num_id
        FROM
            os_usr.v_lst_regions_enf f
        UNION ALL
        SELECT
            device_group_id,
            DECODE( par_group_id, 70656, os_usr.f_get_group_reg_param( device_group_id ), par_group_id ) par_group_id,
            group_type_id,
            group_name,
            os_usr.f_get_group_reg_param(device_group_id) reg,
            null AS num_id
        FROM
            (SELECT * FROM (SELECT * FROM os_eqm.device_groups)
             CONNECT BY PRIOR device_group_id = NVL( par_group_id, 0 ) START WITH device_group_id = 70656
            )
        WHERE
            group_type_id IN(86,67) AND group_name NOT LIKE 'AN%'
        ORDER BY num_id, par_group_id, group_name
    '''
    df = dbexecute(query).fillna('')

    from anytree import Node, RenderTree
    from anytree.exporter import JsonExporter
    from anytree.search import find_by_attr

    groups = [Node("root")]
    errors = []
    for index, row in df.iterrows():
        if not row['par_group_id']:
            groups.append(Node(row['group_name'],parent=groups[0],id=row['device_group_id']))
        else:
            parent = find_by_attr(groups[0], name='id', value=row['par_group_id'])
            if parent:
                groups.append(Node(row['group_name'],parent=parent,id=row['device_group_id']))
            else:
                errors.append(row)
    for row in errors:
        parent = find_by_attr(groups[0], name='id', value=row['par_group_id'])
        groups.append(Node(row['group_name'],parent=parent,id=row['device_group_id']))

    JsonExporter(indent=2, sort_keys=True).write(groups[0], open('static/groups.json','w'))
"""
