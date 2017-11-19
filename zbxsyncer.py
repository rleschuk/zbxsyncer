#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, sys, time, json, re
from config import *
for env in ENV: os.environ[env] = ENV[env]
from libs.zapi import Zapi, ZapiAttrException
from libs.datapi import Datapi
from libs.rabbitmq import Publisher, Consumer
from libs.utils import *
from flask import Flask, render_template, flash, redirect, url_for, session, logging, request, jsonify, abort
from apscheduler.schedulers.background import BackgroundScheduler
#from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import atexit
import logging
logging.basicConfig(
    format     = LOG_FORMAT,
    level      = LOG_LEVEL,
    filename   = LOG_FILE
)
logging.info(PATH)
app = Flask(__name__)

consumers = []
for index in xrange(CONSUMERS_COUNT):
    consumers.append(Consumer(consumer_name='Consumer-%s' % (index + 1)))
    #consumers[index].setName('Consumer-%s' % (index + 1))
    consumers[index].setDaemon(True)
    consumers[index].start()

def sync_all():
    publisher = Publisher()
    datapi = Datapi()
    if publisher.is_zero_queue():
        timestamp = int(time.time())
        chunksize = 100
        chunks = datapi.GetDataViaOracle(SQL_SELECT_DEVICES.format(''), chunksize=chunksize)
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
                logging.debug('publish device to sync {0:07d}/{1}'.format(index+offset+1, eqm_device['host']))
                if eqm_device['device_ip']:
                    eqm_hosts.append(eqm_device['host'])
        zbx_hosts = Zapi().get_all_host()
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
                    logging.debug('publish device to delete {0:07d}/{1}'.format(index+1, host['host']))
    publisher.close()

def check_proxy_status():
    for consumer in consumers:
        consumer.zbx.init_proxy()

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=sync_all,
    trigger=CronTrigger(hour='*/2'),
    #trigger=CronTrigger(minute='*/5'),
    id='sync_all',
    name='sync_all',
    replace_existing=True
)
scheduler.add_job(
    func=check_proxy_status,
    trigger=CronTrigger(minute='*/10'),
    id='check_proxy_status',
    name='check_proxy_status',
    replace_existing=True
)

def save_exit():
    try:
        for consumer in consumers:
            consumer.shutdown()
            #consumer.join()
        scheduler.shutdown()
    except:
        pass

atexit.register(save_exit)

@app.route('/')
def home():
    return 'OK'

@app.route('/sync_by_device_id')
def sync_by_device_id():
    error = ''
    eqm_device = None
    zbx_device = None
    params = []
    timestamp = int(time.time())
    if not is_int(request.args.get('device_id')):
        return jsonify(error='incorrect argument device_id',timestamp=timestamp)
    try:
        eqm_device = Datapi().GetDataViaOracle(
            SQL_SELECT_DEVICES.format('and d.device_id = {0}'.format(request.args.get('device_id')))
        )
        if eqm_device.empty:
            eqm_device = None
        else:
            eqm_device = eqm_device.to_dict(orient='records')[0]
            try:
                Publisher().check_process(eqm_device, timestamp)
            except Exception as e:
                logging.error(repr(e))
            zbx = Zapi()
            zbx_device = zbx.get_host(eqm_device)
            if len(zbx_device): zbx_device = zbx_device[0]
            else: zbx_device = None
            params = zbx.sync_host(eqm_device, zbx_device)
    except Exception as e:
        logging.error(u'{0} {1}'.format(eqm_device['host'], repr(e)))
        error = repr(e)
    return jsonify(
        eqm_device=eqm_device,
        zbx_device=zbx_device,
        error=error,
        params=params,
        timestamp=timestamp
    )

if __name__ == '__main__':
    app.secret_key = APP_SECRET_KEY
    app.debug = APP_DEBUG
    app.run(host=APP_HOST, port=APP_PORT, threaded=APP_THREADED)
