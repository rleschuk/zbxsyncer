import os


class Config:
    # Define dirnames
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    TMP_DIR = os.path.join(BASE_DIR, 'tmp')

    # Define the application log
    LOG_FILENAME = os.path.join(TMP_DIR, 'app.log')
    LOG_FORMAT = "%(asctime)s {%(module)s:%(lineno)d} %(levelname)s - %(message)s"
    LOG_LEVEL = 'INFO'

    # Define secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'zbxsyncer'

    # Enable protection agains *Cross-site Request Forgery (CSRF)*
    #CSRF_ENABLED = True

    # Use a secure, unique and absolutely secret key for
    # signing the data.
    #CSRF_SESSION_KEY = "zbxsyncer"

    # Define mail services
    #ADMIN = os.environ.get('ADMIN')
    #MAIL_SERVER = os.environ['MAIL_SERVER']
    #MAIL_PORT = int(os.environ['MAIL_PORT'])
    #MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    #MAIL_USERNAME = os.environ['MAIL_USERNAME']
    #MAIL_PASSWORD = os.environ['MAIL_PASSWORD']
    #MAIL_SUBJECT_PREFIX = os.environ.get('MAIL_SUBJECT_PREFIX') or '[zbxsyncer]'
    #MAIL_SENDER = os.environ.get('MAIL_SENDER') or 'Zbxsyncer Admin'

    # Application threads. A common general assumption is
    # using 2 per available processor cores - to handle
    # incoming requests using one and performing background
    # operations using the other.
    THREADS_PER_PAGE = 5

    # RabbitMQ configuration
    RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST') or 'localhost'
    RABBITMQ_USER = os.environ.get('RABBITMQ_USER') or 'guest'
    RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS') or 'guest'
    RABBITMQ_QUEUE = 'zbxsyncer'
    RABBITMQ_ERRDELAY = 5
    RABBITMQ_ATTEMPTS = 3
    RABBITMQ_CONSUMERS = 4

    # ZabbixAPI configuration
    ZABBIX_URL = os.environ['ZABBIX_URL']
    ZABBIX_USER = os.environ['ZABBIX_USER']
    ZABBIX_PASS = os.environ['ZABBIX_PASS']
    MONITORING_ICMP = os.environ.get('MONITORING_ICMP') or '2102'
    MONITORING_ADVANCED = os.environ.get('MONITORING_ADVANCED') or '2103'
    MONITORING_DISABLED = os.environ.get('MONITORING_DISABLED') or '2101'
    MONITORING_ICMP_TEMPLATEIDS = {
        'default': [10176],
        'breezemaxcpe': [],
    }
    DEFAULT_TEMPLATEIDS = {
        'default': [10177],
        'breezemaxcpe': [],
    }
    DEFAULT_MACROSES = [
        { 'macro': '{$SNMP_COMMUNITY}', 'value': os.environ['DEFAULT_SNMP_COMMUNITY'] },
        { 'macro': '{$ICMP_PING_LOSS_LIMIT}', 'value': 10 },
        { 'macro': '{$ICMP_PING_RESPONSE_LIMIT}', 'value': 0.15 },
    ]

    # SQL configuration
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
        inner join (
            select distinct department_id
            from os_usr.zbxsyncer_groups
        ) s on na.segment = s.department_id
    where
        na.is_management = 1
        {0}
    """
    # Define the database - we are working with
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATABASE_CONNECT_OPTIONS = {}
    FLASHES = []


    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    FLASHES = [('Development mode','warning')]
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_DATABASE_URI = os.environ['DEV_DATABASE_URL']
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
        inner join (
            select distinct department_id
            from os_usr.zbxsyncer_groups
        ) s on na.segment = s.department_id
    where
        na.is_management = 1
        {0}
        --and rownum <= 10000
    """
    RABBITMQ_CONSUMERS = 1


class TestingConfig(Config):
    FLASHES = [('Testing mode','warning')]
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ['TEST_DATABASE_URL']
    RABBITMQ_CONSUMERS = 1


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
