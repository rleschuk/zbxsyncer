import sys, os
import warnings
warnings.simplefilter(action='ignore', category=UserWarning)
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from app import app
from app.libs.pyzabbix import ZabbixAPI
from app.libs.utils import format_data
from datetime import datetime
from time import time
from pandas import DataFrame

class ZapiAttrException(Exception): pass

class Zapi(object):
    def __init__(self):
        self.url = app.config['ZABBIX_URL']
        self.username = app.config['ZABBIX_USER']
        self.password = app.config['ZABBIX_PASS']
        self.conn = None
        self.session_verify = False
        self.proxys_online = []
        self.proxys_offline = []
        self.connect()
        self.init_proxy()

    def connect(self):
        self.conn = ZabbixAPI(self.url)
        self.conn.session.verify = self.session_verify
        self.conn.login(self.username, self.password)

    def _do_request(self, method, params):
        return format_data(self.conn.do_request(method, params)['result'])

    def init_proxy(self, period=600):
        timestamp = int(time()) - period
        proxys = self._do_request('proxy.get', dict(
            output="extend"
        ))
        self.proxys_offline = []
        self.proxys_online = []
        for proxy in proxys:
            if proxy['lastaccess'] < timestamp:
                app.logger.debug('proxy {0} in offline'.format(proxy['proxyid']))
                self.proxys_offline.append(proxy['proxyid'])
            else:
                self.proxys_online.append(proxy['proxyid'])
        return

    def get_host(self, context):
        _filter={'host':[]}
        if type(context) == type([]):
            _filter['host'] = [e['host'] for e in context]
        elif type(context) == type({}):
            _filter['host'] = [context['host']]
        host = self._do_request('host.get', dict(
            output=['hostid','host','name','proxy_hostid','status','snmp_error'],
            filter=_filter,
            selectParentTemplates=['name','templateid'],
            selectGroups=['groupid','name'],
            selectInterfaces=['interfaceid','ip','main','port','type'],
            selectMacros=['hostmacroid','macro','value'],
        ))
        return host

    def get_public_host(self, ip):
        hosts = self._do_request('host.get', dict(
            output=['hostid','host','name'],
            filter={ 'host': [ip] }
        ))
        if hosts:
            for i, host in enumerate(hosts):
                hosts[i]['url'] = "{0}/latest.php?filter_set=1&show_without_data=1&hostids[]={1}".format(
                    self.url,
                    host['hostid']
                )
        return hosts

    def add_public_host(self, ip):
        result = self._do_request('host.create', dict(
            host=ip,
            name=ip,
            proxy_hostid=0,
            groups=[{'groupid': 74}],
            interfaces=[{"type": 2, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": 161}],
            templates=[{'templateid':e} for e in app.config['DEFAULT_TEMPLATEIDS']['default']],
            status=0,
            description='Created {0}'.format(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
        ))
        hosts = self.get_public_host(ip)
        return hosts

    def get_all_host(self):
        hosts = self._do_request('host.get', dict(
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
            params['name'] = u'{0} @{1}'.format(eqm_device['device_name'], eqm_device['host'])
            params['proxy_hostid'] = eqm_device['zbx_proxyid']
            params['groups'] = [{'groupid': eqm_device['zbx_groupid']}]
            params['interfaces'] = [{"type": 2, "main": 1, "useip": 1, "ip": eqm_device['device_ip'], "dns": "", "port": 161}]
            params['macros'] = eqm_device['zbx_macros']
            params['templates'] = [{'templateid':e} for e in eqm_device['zbx_templateids']]
            if eqm_device['monitoring_type'] == app.config['MONITORING_DISABLED']:
                params['status'] = 1
            params['description'] = 'Created {0}'.format(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
            self._do_request('host.create', params)
            app.logger.info('{0} created'.format(eqm_device['host']))
        else:
            if u'{0} @{1}'.format(eqm_device['device_name'], eqm_device['host']) != zbx_device['name']:
                params['name'] = u'{0} @{1}'.format(eqm_device['device_name'], eqm_device['host'])
            if eqm_device['zbx_proxyid'] != zbx_device['proxy_hostid']:
                params['proxy_hostid'] = eqm_device['zbx_proxyid']
            if eqm_device['monitoring_type'] == app.config['MONITORING_DISABLED']:
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
                    app.logger.info(u'{0} update {1} "{2}"'.format(eqm_device['host'], k, params[k]))
                params['hostid'] = zbx_device['hostid']
                params['description'] = 'Updated {0}'.format(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
                self._do_request('host.update', params)
                if 'templates' in params:
                    self.update_items(zbx_device)
                app.logger.info('{0} updated'.format(eqm_device['host']))
        return params

    def update_interface(self, eqm_device, zbx_device):
        interfaces = []
        result = self._do_request('hostinterface.update', dict(
            interfaceid=zbx_device['interfaces'][0]['interfaceid'],
            ip=eqm_device['device_ip']
        ))
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
                    self._do_request('usermacro.update', dict(
                        hostmacroid = zbx_device['macros'][index]['hostmacroid'],
                        value       = l['value']
                    ))
            except ValueError:
                if l['macro'] in [m['macro'] for m in app.config['DEFAULT_MACROSES']]:
                    index = [e['macro'] for e in app.config['DEFAULT_MACROSES']].index(l['macro'])
                    if l['value'] != app.config['DEFAULT_MACROSES'][index]['value']:
                        for_add.append({'hostmacroid': self._do_request('usermacro.create', dict(
                            hostid = zbx_device['hostid'],
                            macro  = l['macro'],
                            value  = l['value']
                        ))['hostmacroids'][0]})
                else:
                    for_add.append({'hostmacroid': self._do_request('usermacro.create', dict(
                        hostid = zbx_device['hostid'],
                        macro  = l['macro'],
                        value  = l['value']
                    ))['hostmacroids'][0]})
        return for_add

    def get_templates(self, eqm_device):
        zbx_templateids = []
        if eqm_device['monitoring_type'] == app.config['MONITORING_ICMP']:
            zbx_templateids = app.config['MONITORING_ICMP_TEMPLATEIDS'][eqm_device['driver']]
        elif not eqm_device['monitoring_type']:
            zbx_templateids = app.config['MONITORING_ICMP_TEMPLATEIDS'][eqm_device['driver']]
        elif not eqm_device['zbx_templateids']:
            zbx_templateids = app.config['DEFAULT_TEMPLATEIDS'][eqm_device['driver']]
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
        return self._do_request('trigger.get', dict(
            lastChangeSince=int(time())-seconds,
            #filter={'value':1},
            output=['description','lastchange','priority','triggerid','value'],
            selectHosts=['hostid','host','name'],
            sortfield='lastchange',
            sortorder='DESC',
            expandDescription=True
        ))

    def update_items(self, zbx_device):
        result = []
        items = self._do_request('item.get', dict(
            host=zbx_device['host'],
            output=['itemid','name','templateid','status'],
            selectItemDiscovery=['parent_itemid']
        ))
        parent_itemids = []
        for item in items:
            try: parent_itemids.append(item['itemDiscovery']['parent_itemid'])
            except: pass
        parent_itemids = list(set(parent_itemids))
        itemprototypes = []
        if parent_itemids:
            itemprototypes = self._do_request('itemprototype.get', dict(
                itemids=parent_itemids,
                output=['itemid'],
                inherited=True,
            ))
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
            self._do_request('item.update', result)
        return result

    def get_items(self, host):
        return self.update_items({'host':host})

    def get_proxy(self, eqm_device):
        if eqm_device['zbx_master_proxyid'] in self.proxys_offline:
            if eqm_device['zbx_slave_proxyid']:
                return eqm_device['zbx_slave_proxyid']
        return eqm_device['zbx_master_proxyid']

    def delete_host(self, hostid):
        return self.conn.host.delete(hostid)

    def get_link_latest(self, host=0, ip=''):
        hostids = []
        if host:
            hostids = self._do_request('host.get', dict(
                output=['hostid','host'],
                filter={ 'host': [host] }
            ))
        elif ip:
            hostids = self._do_request('hostinterface.get', dict(
                output=['hostid','host'],
                filter={ 'ip': [ip] }
            ))
        if hostids:
            return "{0}/latest.php?filter_set=1&show_without_data=1&hostids[]={1}".format(self.url, hostids[0]['hostid'])
        else:
            return "{0}/search.php?search={0}".format(self.url, host)

    """
    def get_items_history(self, host, key='icmpping', time_from=0, time_till=0, period=3600,
                          workonly=False, offset=0, weekdays=[], from_hour=9, till_hour=18):
        result = dict(
            host=host, key=key, workonly=workonly, offset=offset,
            time_from=time_from, time_till=time_till, period=period,
            items=[], weekdays=weekdays, from_hour=9, till_hour=18
        )
        zhost = self._do_request('host.get', dict(
            output=['hostid', 'snmp_available', 'snmp_error'],
            filter={ 'host': [host] }
        ))
        if not zhost: return result
        result.update(zhost[0])
        items = DataFrame(self._do_request('item.get', dict(
            output=['hostid','itemid','name','key_','value_type','lastclock','lastvalue'],
            hostids=[h['hostid'] for h in zhost]
        )))
        items = items[items.key_.str.contains(key, regex=True, na=False)]
        if items.empty: return result
        if time_from and time_till:
            result['period'] = time_till-time_from
            for index, item in items.iterrows():
                history = DataFrame(self._do_request('history.get', dict(
                    history = item['value_type'],
                    itemids = [item['itemid']],
                    time_from = time_from,
                    time_till = time_till,
                    sortfield = "clock"
                )))
                if history.empty: continue
                history.clock = pd.to_numeric(history.clock, errors='coerce')
                history.value = pd.to_numeric(history.value, errors='coerce')
                #if offset: history.clock = history.clock + int(offset)
                #if workonly:
                #    history = history.loc[history['clock'].isin(
                #        filterWorkTimestamp(history.clock.tolist(), offset, weekdays, from_hour, till_hour)
                #    )]
                #print history
                items.set_value(index, 'max', history.value.max())
                items.set_value(index, 'min', history.value.min())
                items.set_value(index, 'avg', history.value.mean())
        result['items'] = items.fillna(0).to_dict(orient='records')
        return result

    def get_chart_cached(self, host, key='icmpping', time_from=0, time_till=0, stime=0, period=3600, width=1000):
        connection = ZabbixAPI(ZURL)
        connection.session.verify = False
        connection.login(USER, PASS)
        items = pd.DataFrame(connection.item.get(
            output=['hostid','itemid','name','key_'],
            hostids=[h['hostid'] for h in connection.host.get(output=['hostid'], filter={ 'host': [host] })]
        ))
        items = items[items.key_.str.contains(key, regex=True, na=False)]
        if items.empty: return 'static/images/fake_chart.png'
        if (time_till and time_from):
            stime = datetime.utcfromtimestamp(float(time_from)).strftime("%Y%m%d%H%M%S")
            period = int(time_till)-int(time_from)
        params = [
            'period='+str(period),
            '&'.join(['itemids['+i+']='+i for i in items['itemid'].tolist()]),
            'type=0',
            'batch=1',
            'updateProfile=0',
            'width=850',
            'height=180'
        ]
        if stime: params.append('stime='+str(stime))
        filename = '{0}_{1}_{2}_{3}.png'.format(host, ''.join(items['itemid'].tolist()), time_from, time_till)
        with requests.session() as c:
            c.post('{0}/index.php?login=1'.format(ZURL), verify=False, data={
                'name': USER,
                'password': PASS,
                'enter': 'Sign in',
                'autologin': '1',
                'request': ''
            })
            #print '{0}/chart.php?{1}'.format(ZURL, '&'.join(params))
            r=c.get('{0}/chart.php?{1}'.format(ZURL, '&'.join(params)))
            with open('static/images/'+filename, 'wb') as img:
                img.write(r.content)
        return 'static/images/'+filename
    """
