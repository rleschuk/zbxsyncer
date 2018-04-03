from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy

import os
import traceback
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config.from_object('config')
setattr(app, 'db', SQLAlchemy(app))
for key, value in app.config.get('ENV', {}).items(): os.environ[key] = value

from app.libs import zapi
from app.libs.datapi import dbexecute
from app.libs.rabbitmq import Publisher, Consumer
#from app.libs.utils import *
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

formatter = logging.Formatter(app.config['LOG_FORMAT'])
handler = RotatingFileHandler(app.config['LOG_FILENAME'], maxBytes=10000000, backupCount=5)
handler.setLevel(app.config['LOG_LEVEL'])
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(app.config['LOG_LEVEL'])

@app.errorhandler(400)
def forbidden(error):
    return 'Bad request', 400

@app.errorhandler(403)
def forbidden(error):
    return 'Forbidden', 403

@app.errorhandler(404)
def not_found(error):
    return 'Not Found', 404

@app.errorhandler(Exception)
def exceptions(e):
    tb = traceback.format_exc()
    app.logger.error('%s %s %s %s\n%s',
        request.remote_addr, request.method,
        request.scheme, request.full_path, tb.strip())
    return "Internal Server Error", 500

from app.blueprints import api
app.register_blueprint(api)

from app.blueprints import reports
app.register_blueprint(reports)

setattr(app, 'consumers', [])
for index in range(app.config['CONSUMERS_COUNT']):
    app.consumers.append(Consumer(consumer_name='Consumer-%s' % (index + 1)))
    #app.consumers[index].setName('Consumer-%s' % (index + 1))
    app.consumers[index].setDaemon(True)
    app.consumers[index].start()

def sync_all():
    import time, re
    publisher = Publisher()
    if publisher.is_zero_queue():
        timestamp = int(time.time())
        chunksize = 100
        chunks = dbexecute(app.config['SQL_SELECT_DEVICES'].format(''), chunksize=chunksize)
        eqm_hosts = []
        for chunk_index, eqm_devices in enumerate(chunks):
            offset = chunk_index * chunksize
            for index, eqm_device in eqm_devices.iterrows():
                publisher.publish(json.dumps(dict(
                    action='sync',
                    data=eqm_device.to_dict(),
                    attempt=1,
                    timestamp=timestamp
                )))
                app.logger.debug('publish device to sync {0:07d}/{1}'.format(index+offset+1, eqm_device['host']))
                if eqm_device['device_ip']:
                    eqm_hosts.append(eqm_device['host'])
        zbx_hosts = zapi.Zapi().get_all_host()
        regex = re.compile(r'@\d+$')
        for index, host in enumerate(zbx_hosts):
            if re.search(regex, host['name']):
                if host['host'] not in eqm_hosts:
                    publisher.publish(json.dumps(dict(
                        action='delete',
                        data=host,
                        attempt=1,
                        timestamp=timestamp
                    )))
                    app.logger.debug('publish device to delete {0:07d}/{1}'.format(index+1, host['host']))
    publisher.close()

def check_proxy_status():
    for consumer in app.consumers:
        consumer.zbx.init_proxy()

setattr(app, 'scheduler', BackgroundScheduler())
app.scheduler.add_job(
    func=sync_all,
    trigger=CronTrigger(hour='*/2'),
    #trigger=CronTrigger(minute='*/5'),
    id='sync_all',
    name='sync_all',
    replace_existing=True
)
app.logger.info('scheduler add job sync_all')
app.scheduler.add_job(
    func=check_proxy_status,
    trigger=CronTrigger(minute='*/10'),
    id='check_proxy_status',
    name='check_proxy_status',
    replace_existing=True
)
app.logger.info('scheduler add job check_proxy_status')

app.scheduler.start()
app.logger.info('scheduler started')

def save_exit():
    try:
        for consumer in app.consumers: consumer.shutdown()
        app.scheduler.shutdown()
        app.logger.info('scheduler has been shut down')
    except Exception as err:
        app.error('save exit error: %s' % repr(err))
atexit.register(save_exit)
app.logger.info('atexit register save_exit')

app.logger.info('initialization finished')
