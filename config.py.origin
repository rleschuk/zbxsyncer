import os
# Application version
VERSION = 0.1
# Statement for enabling the development environment
DEBUG = True
# Define the application directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
# Define the application log
LOG_FILENAME = os.path.join(TMP_DIR, 'app.log')
LOG_FORMAT = "%(asctime)s {%(module)s:%(lineno)d} %(levelname)s - %(message)s"
LOG_LEVEL = 'DEBUG'
# Define the application settings filename
SETTING_FILENAME = os.path.join(BASE_DIR, 'app', 'settings.xml')
# Application threads. A common general assumption is
# using 2 per available processor cores - to handle
# incoming requests using one and performing background
# operations using the other.
THREADS_PER_PAGE = 5
# Enable protection agains *Cross-site Request Forgery (CSRF)*
CSRF_ENABLED = True
# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "zbxsyncer"
# Secret key for signing cookies
SECRET_KEY = "zbxsyncer"
# Environment
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
TEMP_FILE_DIR = BASE_DIR + '/var'
# ZabbixAPI configuration
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
# Oracle configuration
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
# Define the database - we are working with
SQLALCHEMY_DATABASE_URI = 'oracle://%s:%s@%s:%s/%s' % (ORA_USER, ORA_PASS, ORA_HOST, ORA_PORT, ORA_SID)
SQLALCHEMY_TRACK_MODIFICATIONS = False
DATABASE_CONNECT_OPTIONS = {}
