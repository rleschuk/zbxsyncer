import os, logging, time, re, json
from flask import Blueprint, current_app
from config import config as config_

logger = logging.getLogger('app')


from ..libs import rabbitmq
from ..libs import zapi
from ..libs import datapi
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers import SchedulerNotRunningError


class Syncer(object):

    def __init__(self, config=None):
        self.config = config_[os.getenv('FLASK_CONFIG', 'default')] \
            if config is None else config
        self.consumers = []
        self.app = None
        self.scheduler = BackgroundScheduler()


    def init_app(self, app):
        self.app = app

        for i in range(1, self.app.config.get('RABBITMQ_CONSUMERS', 1) + 1):
            consumer = rabbitmq.Consumer(i, self.config)
            consumer.setDaemon(True)
            consumer.start()
            self.consumers.append(consumer)

        self.scheduler.add_job(
            func=self.sync_all,
            trigger=CronTrigger(hour='*/4'),
            #trigger=CronTrigger(minute='*/5'),
            id='sync_all',
            name='sync_all',
            replace_existing=True
        )
        logger.info('scheduler add job sync_all')

        self.scheduler.add_job(
            func=self.check_proxy_status,
            trigger=CronTrigger(minute='*/10'),
            id='check_proxy_status',
            name='check_proxy_status',
            replace_existing=True
        )
        logger.info('scheduler add job check_proxy_status')

        self.scheduler.start()
        logger.info('scheduler started')

        try:
            import uwsgi
            uwsgi.atexit = self.cleanup
        except ImportError:
            import atexit
            atexit.register(self.cleanup)


    def sync_all(self):
        logger.info('sync all started')
        publisher = rabbitmq.Publisher()
        if publisher.is_zero_queue():
            timestamp = int(time.time())
            chunksize = 100
            chunks = datapi.dbexecute(
                self.app.config['SQL_SELECT_DEVICES'].format(''), self.app,
                chunksize=chunksize)
            eqm_hosts = []
            for chunk_index, eqm_devices in enumerate(chunks):
                offset = chunk_index * chunksize
                for index, eqm_device in eqm_devices.iterrows():
                    publisher.publish(json.dumps({
                        'action': 'sync',
                        'data': eqm_device.to_dict(),
                        'attempt': 1,
                        'timestamp': timestamp
                    }))
                    logger.debug('publish device to sync {0:07d}/{1}'\
                        .format(index + offset + 1, eqm_device['host']))
                    if eqm_device['device_ip']:
                        eqm_hosts.append(eqm_device['host'])
            if not self.app.config['DEBUG']:
                zbx_hosts = zapi.Zapi().get_all_host()
                regex = re.compile(r'@\d+$')
                for index, host in enumerate(zbx_hosts):
                    if not re.search(regex, host['name']): continue
                    if host['host'] not in eqm_hosts:
                        publisher.publish(json.dumps({
                            'action': 'delete',
                            'data': host,
                            'attempt': 1,
                            'timestamp': timestamp
                        }))
                        logger.debug('publish device to delete {0:07d}/{1}'\
                            .format(index + 1, host['host']))
        publisher.close()
        logger.info('sync all finished')


    def check_proxy_status(self):
        logger.info('check proxy status')
        for consumer in self.consumers:
            consumer.zbx.init_proxy()


    def cleanup(self):
        for consumer in self.consumers:
            consumer.shutdown()
        try:
            self.scheduler.shutdown()
            logger.info('scheduler has been shut down')
        except SchedulerNotRunningError:
            pass
