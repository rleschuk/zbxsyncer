#!/usr/bin/python
# -*- coding: utf-8 -*-

import warnings
warnings.simplefilter(action='ignore', category=UserWarning)

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from libs.pyzabbix import ZabbixAPI
import pandas as pd
from datetime import datetime
import time
from config import *
from libs.utils import *

import sys
import logging
logger = logging.getLogger(__name__)

class ZapiAttrException(Exception):
    """ generic zapi exception
    """
    pass

class Zapi(object):
    def __init__(self):
        self.conn = None
        self.proxys_online = []
        self.proxys_offline = []
        self.connect()
        self.init_proxy()

    def connect(self):
        self.conn = ZabbixAPI(ZABBIX_URL)
        self.conn.session.verify = False
        self.conn.login(ZABBIX_USER,ZABBIX_PASS)

    def get_host(self, context):
        _filter={'host':[]}
        if type(context) == type([]):
            _filter['host'] = [e['host'] for e in context]
        elif type(context) == type({}):
            _filter['host'] = [context['host']]
        host = format_data(self.conn.host.get(
            output=['hostid','host','name','proxy_hostid','status','snmp_error'],
            filter=_filter,
            selectParentTemplates=['name','templateid'],
            selectGroups=['groupid','name'],
            selectInterfaces=['interfaceid','ip','main','port','type'],
            selectMacros=['hostmacroid','macro','value'],
        ))
        return host

    def get_all_host(self):
        hosts = format_data(self.conn.host.get(
            output=['hostid','host','name']
        ))
        return hosts

    def sync_host(self, eqm_device, zbx_device):
        params = {}
        eqm_device['zbx_templateids'] = self.get_templates(eqm_device)
        eqm_device['zbx_macros'] = self.get_macros(eqm_device)
        eqm_device['zbx_proxyid'] = self.get_proxy(eqm_device)
        if not eqm_device['device_ip']:
            raise ZapiAttrException('incorrect attribute device_ip')
        if zbx_device is None:
            params['host'] = eqm_device['host']
            params['name'] = u'{0} @{1}'.format(utf8(eqm_device['device_name']), eqm_device['host'])
            params['proxy_hostid'] = eqm_device['zbx_proxyid']
            params['groups'] = [{'groupid': eqm_device['zbx_groupid']}]
            params['interfaces'] = [{"type": 2, "main": 1, "useip": 1, "ip": eqm_device['device_ip'], "dns": "", "port": 161}]
            params['macros'] = eqm_device['zbx_macros']
            params['templates'] = [{'templateid':e} for e in eqm_device['zbx_templateids']]
            if eqm_device['monitoring_type'] == MONITORING_DISABLED:
                params['status'] = 1
            params['description'] = 'Created {0}'.format(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
            self.conn.do_request('host.create', params)
            logger.info('{0} created'.format(eqm_device['host']))
        else:
            if u'{0} @{1}'.format(utf8(eqm_device['device_name']), eqm_device['host']) != zbx_device['name']:
                params['name'] = u'{0} @{1}'.format(utf8(eqm_device['device_name']), eqm_device['host'])
            if eqm_device['zbx_proxyid'] != zbx_device['proxy_hostid']:
                params['proxy_hostid'] = eqm_device['zbx_proxyid']
            if eqm_device['monitoring_type'] == MONITORING_DISABLED:
                if zbx_device['status'] == 0:
                    params['status'] = 1
            else:
                if zbx_device['status'] == 1:
                    params['status'] = 0
            if eqm_device['zbx_groupid'] not in [g['groupid'] for g in zbx_device['groups']]:
                params['groups'] = [{'groupid': eqm_device['zbx_groupid']}]
            if eqm_device['device_ip'] not in [i['ip'] for i in zbx_device['interfaces']]:
                params['interfaces'] = self.update_interface(eqm_device, zbx_device)
            (for_add, for_del) = self.check_templates(eqm_device, zbx_device)
            if for_add:
                params['templates'] = [{'templateid':e} for e in for_add]
            #if for_del:
            #    params['templates_clear'] = [{'templateid':e} for e in for_del]
            for_add = self.check_macros(eqm_device, zbx_device)
            if for_add:
                params['macors'] = for_add
            if params:
                for k in params:
                    logger.info(u'{0} update {1} "{2}"'.format(eqm_device['host'], k, params[k]))
                params['hostid'] = zbx_device['hostid']
                params['description'] = 'Updated {0}'.format(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
                self.conn.do_request('host.update', params)
                if 'templates' in params:
                    self.update_items(zbx_device)
                logger.info('{0} updated'.format(eqm_device['host']))
        return params

    def update_interface(self, eqm_device, zbx_device):
        interfaces = []
        result = self.conn.hostinterface.update(
            interfaceid=zbx_device['interfaces'][0]['interfaceid'],
            ip=eqm_device['device_ip']
        )
        interfaces = [{'interfaceid':e} for e in result['interfaceids']]
        return interfaces

    def get_macros(self, eqm_device):
        macros = []
        if eqm_device['macro_snmp_community']:
            macros.append({
                'macro': '{$SNMP_COMMUNITY}',
                'value': eqm_device['macro_snmp_community']
            })
        if eqm_device['macro_icmp_ping_loss_limit']:
            macros.append({
                'macro': '{$ICMP_PING_LOSS_LIMIT}',
                'value': eqm_device['macro_icmp_ping_loss_limit']
            })
        if eqm_device['macro_icmp_ping_response_limit']:
            macros.append({
                'macro': '{$ICMP_PING_RESPONSE_LIMIT}',
                'value': eqm_device['macro_icmp_ping_response_limit']
            })
        return macros

    def check_macros(self, eqm_device, zbx_device):
        for_add = []
        for l in eqm_device['zbx_macros']:
            try:
                index = [e['macro'] for e in zbx_device['macros']].index(l['macro'])
                if l['value'] != zbx_device['macros'][index]['value']:
                    self.conn.usermacro.update(
                        hostmacroid = zbx_device['macros'][index]['hostmacroid'],
                        value       = l['value']
                    )
            except ValueError:
                if l['macro'] in [m['macro'] for m in DEFAULT_MACROSES]:
                    index = [e['macro'] for e in DEFAULT_MACROSES].index(l['macro'])
                    if l['value'] != DEFAULT_MACROSES[index]['value']:
                        for_add.append({'hostmacroid': self.conn.usermacro.create(
                            hostid = zbx_device['hostid'],
                            macro  = l['macro'],
                            value  = l['value']
                        )['hostmacroids'][0]})
                else:
                    for_add.append({'hostmacroid': self.conn.usermacro.create(
                        hostid = zbx_device['hostid'],
                        macro  = l['macro'],
                        value  = l['value']
                    )['hostmacroids'][0]})
        return for_add

    def get_templates(self, eqm_device):
        zbx_templateids = []
        if eqm_device['monitoring_type'] == MONITORING_ICMP:
            zbx_templateids = MONITORING_ICMP_TEMPLATEIDS[eqm_device['driver']]
        elif not eqm_device['monitoring_type']:
            zbx_templateids = MONITORING_ICMP_TEMPLATEIDS[eqm_device['driver']]
        elif not eqm_device['zbx_templateids']:
            zbx_templateids = DEFAULT_TEMPLATEIDS[eqm_device['driver']]
        else:
            try:
                zbx_templateids = [int(e) for e in eqm_device['zbx_templateids'].split(',')]
            except AttributeError:
                zbx_templateids = eqm_device['zbx_templateids']
        return zbx_templateids

    def check_templates(self, eqm_device, zbx_device):
        for_add = []
        for_del = []
        for l in eqm_device['zbx_templateids']:
            if l not in [t['templateid'] for t in zbx_device['parentTemplates']]:
                #for_add.append(int(l))
                for_add = eqm_device['zbx_templateids']
                break
        for r in [t['templateid'] for t in zbx_device['parentTemplates']]:
            if r not in eqm_device['zbx_templateids']:
                for_del.append(r)
        return (for_add, for_del)

    def get_triggers(self, seconds):
        return self.conn.trigger.get(
            lastChangeSince=int(time.time())-seconds,
            #filter={'value':1},
            output=['description','lastchange','priority','triggerid','value'],
            selectHosts=['hostid','host','name'],
            sortfield='lastchange',
            sortorder='DESC',
            expandDescription=True
        )

    def update_items(self, zbx_device):
        result = []
        items = self.conn.item.get(
            host=zbx_device['host'],
            output=['itemid','name','templateid','status'],
            selectItemDiscovery=['parent_itemid'])
        parent_itemids = []
        for item in items:
            try: parent_itemids.append(item['itemDiscovery']['parent_itemid'])
            except: pass
        parent_itemids = list(set(parent_itemids))
        itemprototypes = []
        if parent_itemids:
            itemprototypes = self.conn.itemprototype.get(
                itemids=parent_itemids,
                output=['itemid'],
                inherited=True,
            )
        for item in items:
            try:
                if item['itemDiscovery']['parent_itemid'] in [e['itemid'] for e in itemprototypes]:
                    if item['status'] == '1':
                        result.append({'itemid': item['itemid'], 'status': 0})
                else:
                    if item['status'] == '0':
                        result.append({'itemid': item['itemid'], 'status': 1})
            except:
                if item['templateid'] != '0':
                    if item['status'] == '1':
                        result.append({'itemid': item['itemid'], 'status': 0})
                else:
                    if item['status'] == '0':
                        result.append({'itemid': item['itemid'], 'status': 1})
        if result:
            self.conn.do_request('item.update', result)
        return result

    def get_items(self, host):
        return self.update_items({'host':host})

    def init_proxy(self, offset=600):
        timestamp = int(time.time()) - offset
        proxys = format_data(self.conn.proxy.get(
            output="extend"
        ))
        self.proxys_offline = []
        self.proxys_online = []
        for proxy in proxys:
            if proxy['lastaccess'] < timestamp:
                logger.debug('proxy {0} in offline'.format(proxy['proxyid']))
                self.proxys_offline.append(proxy['proxyid'])
            else:
                self.proxys_online.append(proxy['proxyid'])
        return

    def get_proxy(self, eqm_device):
        if eqm_device['zbx_master_proxyid'] in self.proxys_offline:
            if eqm_device['zbx_slave_proxyid'] not in self.proxys_offline:
                return eqm_device['zbx_slave_proxyid']
            else:
                return 0
        return eqm_device['zbx_master_proxyid']

    def delete_host(self, hostid):
        return self.conn.host.delete(hostid)
