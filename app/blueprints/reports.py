from flask import Blueprint, jsonify, request, abort, redirect, flash, render_template
from app import app
from app.libs.datapi import dbexecute

from datetime import datetime, timedelta

reports = Blueprint('reports', __name__, url_prefix='/reports')

QUERY = {
    'bs_load': '''
        select rownum, devs.* from
            (select
                dig.device_id,
                dig.device_group_id,
                regs.enf_region_name as region,
                os_eqm.grp_utils.f_get_group_name(ds_dgrp.par_group_id) as city,
                os_eqm.grp_utils.f_get_group_name(dig.device_group_id) as full_bs_name,
                rdv.device_name,
                rdv.dc_name,
                rdv.dt_name,
                rdv.ip_addr as ip_addr,
                os_usr.f_get_parent_dev(dig.device_id,'chastota') chastota,
                os_usr.f_get_parent_dev(dig.device_id,'passband') passband,
                calc_load.dev_value as l_load,
                calc_cpe.dev_value as l_cpe,
                null as cpecount, null as cpeutil,
                null as uplink, null as downlink, null as maxuplink, null as maxdownlink,
                null as uputil, null as downutil, null as maxuputil, null as maxdownutil, null as util, null as maxutil,
                null as snmp_available, null as error
            from
                device_in_groups dig
                inner join root_devices_view rdv on dig.device_id = rdv.device_id
                left join os_eqm.device_groups ds_dgrp on ds_dgrp.device_group_id = dig.device_group_id
                left join (select header_id, enf_region_name from os_eqm.groups_86
                           left join os_usr.lst_regions_enf on region_enforty = rec_id) regs on regs.header_id = ds_dgrp.par_group_id
                left join (select rst.dev_value, rst.dev_type_id, rsfc.col_caption from os_usr.ref_sector_thresholds rst
                           inner join os_usr.ref_sector_fr_columns rsfc on rsfc.col_code = rst.col_code
                           where ref_tag = 'A') calc_load on calc_load.dev_type_id = rdv.device_type
                           and calc_load.col_caption = os_usr.f_get_parent_dev(dig.device_id,'passband')
                left join (select rst.dev_value, rst.dev_type_id, rsfc.col_caption from os_usr.ref_sector_thresholds rst
                           inner join os_usr.ref_sector_fr_columns rsfc on rsfc.col_code = rst.col_code
                           where ref_tag = 'B') calc_cpe on calc_cpe.dev_type_id = rdv.device_type
                           and calc_cpe.col_caption = os_usr.f_get_parent_dev(dig.device_id,'passband')
            where
                dig.device_group_id in (
                    select device_group_id from os_eqm.device_groups
                    connect by prior device_group_id = nvl(par_group_id, 0)
                    start with device_group_id in ({groups})
                ) and
                regexp_like(rdv.device_name,'^(sec|idu_sec)', 'i')
            order by
                regs.enf_region_name,
                os_eqm.grp_utils.f_get_group_name(ds_dgrp.par_group_id),
                os_eqm.grp_utils.f_get_group_name(dig.device_group_id),
                rdv.device_name) devs
    '''
}

@reports.context_processor
def inject_datetime(): return dict(datetime=datetime, timedelta=timedelta)

@reports.route('/bs_load', methods=['GET'])
def bs_load():
    flash('Инструмент в стадии тестирования','warning')
    return render_template('bs_load.html')

@reports.route('/get_devices/<key>', methods=['GET'])
def get_devices(key):
    query = QUERY.get(key, '').format(**request.args.to_dict())
    df = dbexecute(query).fillna('')
    return jsonify(get_devices=df.to_dict(orient='records'))

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
