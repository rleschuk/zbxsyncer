import os
PATH = os.path.dirname(os.path.abspath(__file__))

# Configuration of application
# Logging:
LOG_FILE = '/tmp/zbxsyncer.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
# Flask Application:
APP_SECRET_KEY = 'zbxsyncer'
APP_HOST = '0.0.0.0'
APP_DEBUG = False
APP_THREADED = True
APP_PORT = 5001
# Environment:
ENV = {
    'NLS_LANG': '.UTF8',
    'LD_LIBRARY_PATH': '/usr/lib/oracle/12.1/client64/lib',
    'ORACLE_HOME': '/usr/lib/oracle/12.1/client64',
}
# RabbitMQ configuration
RABBITMQ_HOST = 'localhost'
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'
RABBITMQ_QUEUE = 'zbxsyncer'
RABBITMQ_ERRDELAY = 5
RABBITMQ_ATTEMPTS = 3
CONSUMERS_COUNT = 4
TEMP_FILE_DIR = PATH + '/var'
# ZabbixAPI configuration:
ZABBIX_URL = 'https://zabbix.enforta.net'
ZABBIX_USER = 'admin'
ZABBIX_PASS = 'yzv.yj,fyuf'
MONITORING_ICMP = '2102'
MONITORING_ADVANCED = '2103'
MONITORING_DISABLED = '2101'
MONITORING_ICMP_TEMPLATEIDS = {
    'default': [10176],
    'breezemaxcpe': [],
}
DEFAULT_TEMPLATEIDS = {
    'default': [10177],
    'breezemaxcpe': [],
}
DEFAULT_MACROSES = [
    { 'macro': '{$SNMP_COMMUNITY}', 'value': 'engforta' },
    { 'macro': '{$ICMP_PING_LOSS_LIMIT}', 'value': 10 },
    { 'macro': '{$ICMP_PING_RESPONSE_LIMIT}', 'value': 0.15 },
]
# Oracle configuration:
ORA_USER = 'os_sys'
ORA_PASS = 'os_sys'
ORA_HOST = '192.168.66.38'
ORA_PORT = '1521'
ORA_SID  = 'orange'
SQL_SELECT_DEVICES = """
select
    da.device_id as host, d.device_type,
    substr(d.device_name, 1, 128-(length(da.device_id)+2)) as device_name,
    os_usr.zbxsyncer_get_ip(d.device_id) as device_ip,
    na.segment as department_id,
    os_usr.f_get_parent_dev(d.device_id,'mon_zabbix') monitoring_type,
    os_lib.wf_decode_pass(os_usr.f_get_parent_dev(da.device_id,'read_community')) macro_snmp_community,
    os_usr.f_get_parent_dev(d.device_id,'zp_icmp_ping_loss_limit') macro_icmp_ping_loss_limit,
    os_usr.f_get_parent_dev(d.device_id,'zp_icmp_ping_response_lim') macro_icmp_ping_response_limit,
    os_usr.zbxsyncer_get_groupname(d.device_id) as group_name,
    os_usr.zbxsyncer_get_groupid(d.device_id) as zbx_groupid,
    os_usr.zbxsyncer_get_proxyid(d.device_id) as zbx_master_proxyid,
    os_usr.zbxsyncer_get_slave_proxyid(d.device_id) as zbx_slave_proxyid,
    os_usr.zbxsyncer_get_templateids(d.device_type) as zbx_templateids,
    nvl(os_usr.zbxsyncer_get_driver(d.device_id),'default') as driver
from
    devices_active da
    inner join devices d on d.device_id = da.device_id
    inner join net_addresses na on na.device_id = da.device_id
    inner join (select distinct department_id
                from os_usr.zbxsyncer_groups) s on na.segment = s.department_id
where
    na.is_management = 1
    {0}
"""
