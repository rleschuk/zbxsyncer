#!/usr/bin/python
# -*- coding: utf-8 -*-

from config import *
from libs.zapi import Zapi, ZapiAttrException
import pika
import json
import threading
import logging
import os
import time
logger = logging.getLogger(__name__)

class Publisher(object):
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self.connect()

    def __del__(self):
        self.close()

    def connect(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        self.channel = self.connection.channel()
        self.queue = self.channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    def publish(self, body):
        if self.connection.is_closed:
            self.connect()
        self.channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE,
            body=body
        )

    def is_zero_queue(self):
        if self.connection.is_closed:
            self.connect()
        if self.queue.method.message_count == 0:
            return True
        else:
            return False

    def check_process(self, eqm_device, timestamp):
        if self.connection.is_closed:
            self.connect()
        if self.queue.method.message_count == 0:
            try:
                os.remove('{0}/{1}.json'.format(TEMP_FILE_DIR, eqm_device['host']))
            except:
                pass
        else:
            with open('{0}/{1}.json'.format(TEMP_FILE_DIR, eqm_device['host']), 'w') as tempfile:
                json.dump({'timestamp': timestamp, 'eqm_device': eqm_device}, tempfile)

    def close(self):
        try: self.connection.close()
        except: pass

class Consumer(threading.Thread):
    def __init__(self, consumer_name=None):
        self.consumer_name = consumer_name
        self.host = RABBITMQ_HOST
        self.username = RABBITMQ_USER
        self.password = RABBITMQ_PASS
        self.queue = RABBITMQ_QUEUE
        self.connection = None
        self.connected = False
        self.do = True
        self.error_delay = RABBITMQ_ERRDELAY
        self.connection_parameters = pika.ConnectionParameters(
            host=self.host,
            credentials=pika.PlainCredentials(
                username=self.username,
                password=self.password,
                erase_on_connect=False
            )
        )
        self.channel = None
        threading.Thread.__init__(self, name=self.consumer_name)
        self.zbx = None

    def connect(self):
        while not self.connected:
            logger.info('{0} connecting to RabbitMQ...'.format(self.getName()))
            try:
                self.connection = pika.BlockingConnection(parameters=self.connection_parameters)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue, durable=True)
                self.channel.basic_qos(prefetch_count=1)
                self.connected = True
                logger.info('{0} connected to RabbitMQ'.format(self.getName()))
            except Exception as why:
                logger.info('{0} cannot connect to RabbitMQ: {1}'.format(self.getName(), repr(why)))
            time.sleep(self.error_delay)

    def disconnect(self):
        logger.info('{0} disconnecting from RabbitMQ...'.format(self.getName()))
        try:
            self.connection.close()
        except Exception as why:
            pass
        logger.info('{0} disconnected from RabbitMQ'.format(self.getName()))
        self.connected = False

    def reconnect(self):
        self.disconnect()
        self.connect()

    def run(self):
        logger.info('{0} started'.format(self.getName()))
        #self.channel.start_consuming()
        if not self.zbx: self.zbx = Zapi()
        if not self.connected: self.connect()
        while self.do:
            #self.channel.basic_consume(self.callback, queue=RABBITMQ_QUEUE, no_ack=False)
            try:
                self.channel.basic_consume(self.callback, queue=self.queue, no_ack=False)
                while self.do:
                    self.connection.process_data_events()
            except Exception:
                self.reconnect()

    def shutdown(self):
        #self.channel.stop_consuming()
        self.do = False
        logger.info('{0} has been shut down'.format(self.getName()))

    def callback(self, ch, method, properties, body):
        task = json.loads(body)
        try:
            eqm_device = task['data']
            if task['action'] == 'sync':
                if self.check_process(eqm_device, task['timestamp']):
                    zbx_device = self.zbx.get_host(eqm_device)
                    if len(zbx_device):
                        zbx_device = zbx_device[0]
                    else:
                        zbx_device = None
                    params = self.zbx.sync_host(eqm_device, zbx_device)
            elif task['action'] == 'delete':
                result = self.zbx.delete_host(eqm_device['hostid'])
                logger.info('{0} removed'.format(eqm_device['host']))
        except ZapiAttrException as e:
            logger.debug('{0} {1}'.format(eqm_device['host'], repr(e)))
        except Exception as e:
            logger.error('{0} {1}'.format(eqm_device['host'], repr(e)))
            task['attempt'] += 1
            if task['attempt'] <= RABBITMQ_ATTEMPTS:
                self.channel.basic_publish(
                    exchange='',
                    routing_key=RABBITMQ_QUEUE,
                    body=json.dumps(task)
                )
        ch.basic_ack(delivery_tag = method.delivery_tag)

    def check_process(self, eqm_device, timestamp):
        try:
            data = None
            with open('{0}/{1}.json'.format(TEMP_FILE_DIR, eqm_device['host'])) as tempfile:
                data = json.load(tempfile)
            os.remove('{0}/{1}.json'.format(TEMP_FILE_DIR, eqm_device['host']))
            if int(data['timestamp']) < int(timestamp):
                return True
            else:
                return False
        except:
            return True
