
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
