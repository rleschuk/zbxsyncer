import pika
import json
import threading
import os
import time
import logging
from config import config as config_

logger = logging.getLogger('app')

from .zapi import Zapi, ZapiAttrException

class Publisher(object):

    def __init__(self, config=None):
        self.config = config_[os.getenv('FLASK_CONFIG', 'default')] \
            if config is None else config
        self.connection = None
        self.channel = None
        self.connect()


    def connect(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.config.RABBITMQ_HOST))
        self.channel = self.connection.channel()
        self.queue = self.channel.queue_declare(
            queue=self.config.RABBITMQ_QUEUE, durable=True)


    def publish(self, body):
        if self.connection.is_closed: self.connect()
        self.channel.basic_publish(
            exchange = '',
            routing_key = self.config.RABBITMQ_QUEUE,
            body = body
        )


    def is_zero_queue(self):
        if self.connection.is_closed: self.connect()
        if self.queue.method.message_count == 0: return True
        else: return False


    def check_process(self, eqm_device, timestamp, **kwargs):
        if self.connection.is_closed: self.connect()
        filename = os.path.join(self.config.TMP_DIR, '%s.json' % eqm_device['host'])
        if self.queue.method.message_count == 0:
            try: os.remove(filename)
            except Exception: pass
        else:
            with open(filename, 'w') as f:
                json.dump({'timestamp': timestamp, 'eqm_device': eqm_device}, f)


    def close(self):
        try: self.connection.close()
        except Exception: pass


class Consumer(threading.Thread):

    def __init__(self, consumer_name, config=None):
        self.consumer_name = 'Consumer - %s' % consumer_name
        self.config = config_[os.getenv('FLASK_CONFIG', 'default')] \
            if config is None else config
        self.connection = None
        self.connected = False
        self.do = True
        self.connection_parameters = pika.ConnectionParameters(
            host=self.config.RABBITMQ_HOST,
            credentials=pika.PlainCredentials(
                username=self.config.RABBITMQ_USER,
                password=self.config.RABBITMQ_PASS,
                erase_on_connect=False
            )
        )
        self.channel = None
        threading.Thread.__init__(self, name=self.consumer_name)
        self.zbx = None


    def connect(self):
        while not self.connected:
            try:
                self.connection = pika.BlockingConnection(parameters=self.connection_parameters)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.config.RABBITMQ_QUEUE, durable=True)
                self.channel.basic_qos(prefetch_count=1)
                self.connected = True
                logger.info('%s connected to RabbitMQ', self.getName())
            except Exception as why:
                logger.info('%s cannot connect to RabbitMQ: %s', self.getName(), repr(why))
            time.sleep(self.config.RABBITMQ_ERRDELAY)


    def disconnect(self):
        try: self.connection.close()
        except Exception as why: pass
        logger.info('%s disconnected from RabbitMQ', self.getName())
        self.connected = False


    def reconnect(self):
        self.disconnect()
        self.connect()


    def run(self):
        logger.info('%s started', self.getName())
        #self.channel.start_consuming()
        if not self.zbx: self.zbx = Zapi(self.config)
        if not self.connected: self.connect()
        while self.do:
            #self.channel.basic_consume(self.callback, queue=RABBITMQ_QUEUE, no_ack=False)
            try:
                self.channel.basic_consume(self.callback,
                    queue=self.config.RABBITMQ_QUEUE, no_ack=False)
                while self.do:
                    self.connection.process_data_events()
                    time.sleep(0.1)
            except Exception as err:
                logger.error('%s error: %s', self.getName(), repr(err))
                self.reconnect()


    def shutdown(self):
        #self.channel.stop_consuming()
        self.do = False
        logger.info('%s has been shut down', self.getName())


    def callback(self, ch, method, properties, body):
        task = json.loads(body.decode('utf8'))
        try:
            eqm_device = task['data']
            if task['action'] == 'sync':
                if self.check_process(eqm_device, task['timestamp']):
                    zbx_device = self.zbx.get_host(eqm_device)
                    if len(zbx_device): zbx_device = zbx_device[0]
                    else: zbx_device = None
                    self.zbx.sync_host(eqm_device=eqm_device,
                                       zbx_device=zbx_device)
            elif task['action'] == 'delete':
                result = self.zbx.delete_host(eqm_device['hostid'])
                logger.info('%s removed', eqm_device['host'])
        except ZapiAttrException as err:
            logger.debug('%s %s', eqm_device['host'], repr(err))
        except Exception as err:
            logger.error('%s %s', eqm_device['host'], repr(err))
            task['attempt'] += 1
            if task['attempt'] <= self.config.RABBITMQ_ATTEMPTS:
                self.channel.basic_publish(
                    exchange = '',
                    routing_key = self.config.RABBITMQ_QUEUE,
                    body = json.dumps(task)
                )
        ch.basic_ack(delivery_tag = method.delivery_tag)


    def check_process(self, eqm_device, timestamp):
        try:
            data = None
            filename = os.path.join(self.config.TMP_DIR, '%s.json' % eqm_device['host'])
            with open(filename) as f:
                data = json.load(f)
            os.remove(filename)
            if int(data['timestamp']) < int(timestamp): return True
            else: return False
        except Exception as err:
            return True
