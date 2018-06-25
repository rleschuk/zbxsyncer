import sys, os, logging
import warnings
warnings.simplefilter(action='ignore', category=UserWarning)
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from .datapi import dbexecute
from .pyzabbix import ZabbixAPI
from ..utils import format_data
from datetime import datetime
from time import time
from pandas import DataFrame, to_numeric
from io import BytesIO
from config import config as config_
from flask import current_app

logger = logging.getLogger('app')


class ZapiAttrException(Exception): pass


class Zapi(object):

    def __init__(self, config=None):
        self.config = config_[os.getenv('FLASK_CONFIG', 'default')] \
            if config is None else config
        self.conn = None
        self.session_verify = False
        self.proxys_online = []
        self.proxys_offline = []
        self.connect()
        self.init_proxy()


    def connect(self):
        self.conn = ZabbixAPI(self.config.ZABBIX_URL)
        self.conn.session.verify = self.session_verify
        self.conn.login(self.config.ZABBIX_USER, self.config.ZABBIX_PASS)


    def _do_request(self, method, params):
        return format_data(self.conn.do_request(method, params)['result'])


    def init_proxy(self, period=600):
        timestamp = int(time()) - period
        proxys = self._do_request('proxy.get', {'output': 'extend'})
        self.proxys_offline = []
        self.proxys_online = []
        for proxy in proxys:
            if proxy['lastaccess'] < timestamp:
                self.proxys_offline.append(proxy['proxyid'])
            else:
                self.proxys_online.append(proxy['proxyid'])
        return


    def get_host(self, context):
        _filter={'host':[]}
        if isinstance(context, list):
            _filter['host'] = [e['host'] for e in context]
        elif isinstance(context, dict):
            _filter['host'] = [context['host']]
        return self._do_request('host.get', {
            'output': ['hostid','host','name','proxy_hostid','status','snmp_error'],
            'filter': _filter,
            'selectParentTemplates': ['name','templateid'],
            'selectGroups': ['groupid','name'],
            'selectInterfaces': ['interfaceid','ip','main','port','type'],
            'selectMacros': ['hostmacroid','macro','value'],
        })


    def get_all_host(self):
        return self._do_request('host.get', {'output': ['hostid','host','name']})


    def sync_host(self, **kwargs):
        params = {}
        eqm_device = kwargs.get('eqm_device')
        if not eqm_device: return params
        eqm_device['zbx_templateids'] = self.get_templates(eqm_device)
        eqm_device['zbx_macros'] = self.get_macros(eqm_device)
        eqm_device['zbx_proxyid'] = self.get_proxy(eqm_device)
        if not eqm_device['device_ip']:
            raise ZapiAttrException('incorrect attribute: device_ip')
        zbx_device = kwargs.get('zbx_device')
        if zbx_device is None:
            params['host'] = eqm_device['host']
            params['name'] = '%s @%s' % (eqm_device['device_name'], eqm_device['host'])
            params['proxy_hostid'] = eqm_device['zbx_proxyid']
            params['groups'] = [{'groupid': eqm_device['zbx_groupid']}]
            params['interfaces'] = [{"type": 2, "main": 1, "useip": 1, "ip": eqm_device['device_ip'], "dns": "", "port": 161}]
            params['macros'] = eqm_device['zbx_macros']
            params['templates'] = [{'templateid':e} for e in eqm_device['zbx_templateids']]
            if eqm_device['monitoring_type'] == self.config.MONITORING_DISABLED:
                params['status'] = 1
            params['description'] = 'Created %s' % datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            self._do_request('host.create', params)
            logger.info('%s created', eqm_device['host'])
        else:
            if '%s @%s' % (eqm_device['device_name'], eqm_device['host']) != zbx_device['name']:
                params['name'] = '%s @%s' % (eqm_device['device_name'], eqm_device['host'])
            if eqm_device['zbx_proxyid'] != zbx_device['proxy_hostid']:
                params['proxy_hostid'] = eqm_device['zbx_proxyid']
            if eqm_device['monitoring_type'] == self.config.MONITORING_DISABLED:
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
            for_add = self.check_macros(eqm_device, zbx_device)
            if for_add:
                params['macors'] = for_add
            if params:
                for k in params:
                    logger.info('%s update %s "%s"', eqm_device['host'], k, params[k])
                params['hostid'] = zbx_device['hostid']
                params['description'] = 'Updated %s' % datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                self._do_request('host.update', params)
                if 'templates' in params:
                    self.update_items(zbx_device)
                logger.info('%s updated', eqm_device['host'])
        return params


    def update_interface(self, eqm_device, zbx_device):
        return [{'interfaceid':e} for e in self._do_request(
            'hostinterface.update', {
                'interfaceid': zbx_device['interfaces'][0]['interfaceid'],
                'ip': eqm_device['device_ip']
        })['interfaceids']]


    def get_macros(self, eqm_device):
        macros = []
        if eqm_device.get('macro_snmp_community'):
            macros.append({'macro': '{$SNMP_COMMUNITY}',
                           'value': eqm_device['macro_snmp_community']})
        if eqm_device.get('macro_icmp_ping_loss_limit'):
            macros.append({'macro': '{$ICMP_PING_LOSS_LIMIT}',
                           'value': eqm_device['macro_icmp_ping_loss_limit']})
        if eqm_device.get('macro_icmp_ping_response_limit'):
            macros.append({'macro': '{$ICMP_PING_RESPONSE_LIMIT}',
                           'value': eqm_device['macro_icmp_ping_response_limit']})
        return macros


    def check_macros(self, eqm_device, zbx_device):
        for_add = []
        for l in eqm_device.get('zbx_macros', []):
            try:
                index = [e['macro'] for e in zbx_device['macros']].index(l['macro'])
                if l['value'] != zbx_device['macros'][index]['value']:
                    self._do_request('usermacro.update', {
                        'hostmacroid': zbx_device['macros'][index]['hostmacroid'],
                        'value': l['value']
                    })
            except ValueError:
                if l['macro'] in [m['macro'] for m in self.config.DEFAULT_MACROSES]:
                    index = [e['macro'] for e in self.config.DEFAULT_MACROSES].index(l['macro'])
                    if l['value'] != self.config.DEFAULT_MACROSES[index]['value']:
                        for_add.append({'hostmacroid': self._do_request('usermacro.create', {
                            'hostid': zbx_device['hostid'],
                            'macro': l['macro'],
                            'value': l['value']
                        })['hostmacroids'][0]})
                else:
                    for_add.append({'hostmacroid': self._do_request('usermacro.create', {
                        'hostid': zbx_device['hostid'],
                        'macro': l['macro'],
                        'value': l['value']
                    })['hostmacroids'][0]})
        return for_add


    def get_templates(self, eqm_device):
        zbx_templateids = []
        if eqm_device.get('monitoring_type') == self.config.MONITORING_ICMP:
            zbx_templateids = self.config.MONITORING_ICMP_TEMPLATEIDS[eqm_device['driver']]
        elif not eqm_device.get('monitoring_type'):
            zbx_templateids = self.config.MONITORING_ICMP_TEMPLATEIDS[eqm_device['driver']]
        elif not eqm_device.get('zbx_templateids'):
            zbx_templateids = self.config.DEFAULT_TEMPLATEIDS[eqm_device['driver']]
        else:
            try:
                zbx_templateids = [int(e) for e in eqm_device['zbx_templateids'].split(',')]
            except AttributeError:
                zbx_templateids = eqm_device['zbx_templateids']
        return zbx_templateids


    def check_templates(self, eqm_device, zbx_device):
        for_add = []
        for_del = []
        for l in eqm_device.get('zbx_templateids', []):
            if l not in [t['templateid'] for t in zbx_device['parentTemplates']]:
                for_add = eqm_device['zbx_templateids']
                break
        for r in [t['templateid'] for t in zbx_device['parentTemplates']]:
            if r not in eqm_device['zbx_templateids']:
                for_del.append(r)
        return (for_add, for_del)


    def get_triggers(self, seconds):
        return self._do_request('trigger.get', {
            'lastChangeSince': int(time()) - seconds,
            'output': ['description','lastchange','priority','triggerid','value'],
            'selectHosts': ['hostid','host','name'],
            'sortfield': 'lastchange',
            'sortorder': 'DESC',
            'expandDescription': True
        })


    def update_items(self, zbx_device):
        result = []
        items = self._do_request('item.get', {
            'host': zbx_device['host'],
            'output': ['itemid','name','templateid','status'],
            'selectItemDiscovery': ['parent_itemid']
        })
        parent_itemids = []
        for item in items:
            try: parent_itemids.append(item['itemDiscovery']['parent_itemid'])
            except Exception: pass
        parent_itemids = list(set(parent_itemids))
        itemprototypes = []
        if parent_itemids:
            itemprototypes = self._do_request('itemprototype.get', {
                'itemids': parent_itemids,
                'output': ['itemid'],
                'inherited': True,
            })
        for item in items:
            try:
                if item['itemDiscovery']['parent_itemid'] in [e['itemid'] for e in itemprototypes]:
                    if item['status'] == '1':
                        result.append({'itemid': item['itemid'], 'status': 0})
                else:
                    if item['status'] == '0':
                        result.append({'itemid': item['itemid'], 'status': 1})
            except Exception:
                if item['templateid'] != '0':
                    if item['status'] == '1':
                        result.append({'itemid': item['itemid'], 'status': 0})
                else:
                    if item['status'] == '0':
                        result.append({'itemid': item['itemid'], 'status': 1})
        if result: self._do_request('item.update', result)
        return result


    def get_items(self, host):
        return self.update_items({'host': host})


    def get_proxy(self, eqm_device):
        if eqm_device['zbx_master_proxyid'] in self.proxys_offline:
            if eqm_device['zbx_slave_proxyid']:
                return eqm_device['zbx_slave_proxyid']
        return eqm_device['zbx_master_proxyid']


    def delete_host(self, hostid):
        return self.conn.host.delete(hostid)


    def get_items_history(self, **kwargs):
        zhost = self._do_request('host.get', {
            'output': ['hostid', 'snmp_available', 'snmp_error'],
            'filter': {'host': [kwargs.get('host', 0)]}
        })
        if not zhost: return kwargs
        kwargs.update(zhost[0])
        items = DataFrame(self._do_request('item.get', {
            'output': ['hostid','itemid','name','key_','value_type','lastclock','lastvalue'],
            'hostids': [h['hostid'] for h in zhost]
        }))
        items = items[items.key_.str.contains(
            kwargs.get('key', 'icmpping'), regex=True, na=False)]
        if items.empty: return kwargs
        if kwargs.get('time_from') and kwargs.get('time_till'):
            kwargs['period'] = kwargs['time_till'] - kwargs['time_from']
            for index, item in items.iterrows():
                history = DataFrame(self._do_request('history.get', {
                    'history': item['value_type'],
                    'itemids': [item['itemid']],
                    'time_from': kwargs['time_from'],
                    'time_till': kwargs['time_till'],
                    'sortfield': "clock"
                }))
                if history.empty: continue
                history.clock = to_numeric(history.clock, errors='coerce')
                history.value = to_numeric(history.value, errors='coerce')
                if kwargs.get('workonly', []):
                    history = history.loc[history['clock'].isin(
                        Zapi.filterWorkTimestamp(history.clock.tolist(), **kwargs)
                    )]
                items.set_value(index, 'max', history.value.max())
                items.set_value(index, 'min', history.value.min())
                items.set_value(index, 'avg', history.value.mean())
        kwargs['items'] = items.fillna(0).to_dict(orient='records')
        return kwargs


    @staticmethod
    def filterWorkTimestamp(timestamps, **kwargs):
        filtered = []
        for t in timestamps:
            dt = datetime.utcfromtimestamp(float(t + kwargs.get('offset', 0)))
            if (dt.isoweekday() in kwargs.get('weekdays', [])) \
                    and (dt.hour >= kwargs.get('from_hour', 9) and \
                         dt.hour < kwargs.get('till_hour', 18)):
                filtered.append(t)
        return filtered


    def get_chart_cached(self, **kwargs):
        items = DataFrame(self._do_request('item.get', {
            'output': ['hostid','itemid','name','key_'],
            'hostids': [h['hostid'] for h in self._do_request(
                'host.get', {
                    'output': ['hostid'],
                    'filter': {'host': [kwargs.get('host', 0)]}
                })]
        }))
        items = items[items.key_.str.contains(
            kwargs.get('key', 'icmpping'), regex=True, na=False)]
        if items.empty:
            return os.path.join(
                self.config.BASE_DIR, 'app', 'static', 'images', 'fake_chart.png')
        if kwargs.get('time_from') and kwargs.get('time_till'):
            kwargs['stime'] = datetime.utcfromtimestamp(float(kwargs['time_from']))\
                .strftime("%Y%m%d%H%M%S")
            kwargs['period'] = kwargs['time_till'] - kwargs['time_from']
        with requests.session() as session_:
            session_.post('%s/index.php' % self.config.ZABBIX_URL, verify=False, data={
                'name': self.config.ZABBIX_USER,
                'password': self.config.ZABBIX_PASS,
                'enter': 'Sign in',
                'autologin': '1',
                'request': ''
            }, params={'login': 1})
            params = {
                'period': kwargs.get('period', 3600),
                'stime': kwargs.get('stime', 0),
                'type': 0,
                'batch': 1,
                'updateProfile': 0,
                'width': 850,
                'height': 180
            }
            params.update({'itemids[%s]' % i: i for i in items['itemid'].tolist()})
            response = session_.get('%s/chart.php' % self.config.ZABBIX_URL, params=params)
            bio = BytesIO(response.content)
            bio.name = 'image.png'
            return bio


    def sync_by_device_id(self, **kwargs):
        kwargs['timestamp'] = int(time())
        kwargs['error'] = 'ok'
        kwargs['eqm_device'] = None
        kwargs['zbx_device'] = None
        kwargs['params'] = []
        if not kwargs.get('device_id') or \
                not isinstance(kwargs.get('device_id'), int):
            kwargs['error'] = 'incorrect argument: device_id'
            return kwargs
        try:
            kwargs['eqm_device'] = dbexecute(
                self.config.SQL_SELECT_DEVICES\
                .format('and d.device_id = %s' % kwargs['device_id']), current_app)
            if not kwargs['eqm_device'].empty:
                kwargs['eqm_device'] = kwargs['eqm_device'].to_dict(orient='records')[0]
                try:
                    from .rabbitmq import Publisher
                    Publisher().check_process(**kwargs)
                except Exception as err:
                    logger.error(repr(err))
                kwargs['zbx_device'] = self.get_host(kwargs['eqm_device'])
                if len(kwargs['zbx_device']):
                    kwargs['zbx_device'] = kwargs['zbx_device'][0]
                kwargs['params'] = self.sync_host(**kwargs)
        except Exception as err:
            kwargs['error'] = repr(err)
            logger.error('%s %s', kwargs['device_id'], repr(err))
        return kwargs


    def get_public_host(self, **kwargs):
        kwargs['devices'] = self._do_request('host.get', {
            'output': ['hostid','host','name'],
            'filter': {'host': [kwargs['ip']]}
        })
        for i, host in enumerate(kwargs['devices']):
            kwargs['devices'][i]['url'] = "%s/latest.php?filter_set=1&show_without_data=1&hostids[]=%s" \
                % (self.config.ZABBIX_URL, host['hostid'])
        return kwargs


    def add_public_host(self, **kwargs):
        kwargs['timestamp'] = int(time())
        kwargs['error'] = 'ok'
        kwargs['devices'] = None
        if not kwargs.get('ip'):
            kwargs['error'] = 'incorrect argument: ip'
            return kwargs
        kwargs.update(self.get_public_host(**kwargs))
        if not kwargs['devices']:
            try:
                self._do_request('host.create', {
                    'host': kwargs['ip'],
                    'name': kwargs['ip'],
                    'proxy_hostid': 0,
                    'groups': [{'groupid': 73}],
                    'interfaces': [{"type": 2, "main": 1, "useip": 1,
                                    "ip": kwargs['ip'], "dns": "", "port": 161}],
                    'templates': [{'templateid':e} for e in self.config.DEFAULT_TEMPLATEIDS['default']],
                    'status': 0,
                    'description': 'Created %s' % datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                })
                kwargs.update(self.get_public_host(**kwargs))
            except Exception as err:
                kwargs['error'] = repr(err)
                logger.error(repr(err))
        return kwargs


    def get_link_latest(self, **kwargs):
        hostids = []
        key = 'id'
        if kwargs.get('id') and isinstance(kwargs.get('id'), int):
            hostids = self._do_request('host.get', {
                'output': ['hostid','host'],
                'filter': { 'host': [kwargs.get('id')] }
            })
        elif kwargs.get('ip') and isinstance(kwargs.get('ip'), str):
            key = 'ip'
            hostids = self._do_request('hostinterface.get', {
                'output': ['hostid','host'],
                'filter': { 'ip': [kwargs.get('ip')] }
            })
        return "%s/latest.php?filter_set=1&show_without_data=1&hostids[]=%s" \
            % (self.config.ZABBIX_URL, hostids[0]['hostid']) \
            if hostids else \
            "%s/search.php?search=%s" \
            % (self.config.ZABBIX_URL, kwargs.get(key))
