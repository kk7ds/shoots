import datetime
import json
import logging
import pprint
import socket
import ssl
import threading

import paho.mqtt.client as mqtt

PRINT_STAGE_IDLE = 1
PRINT_STAGE_PRINTING = 2
STAGES = {
    PRINT_STAGE_IDLE: 'Idle',
    PRINT_STAGE_PRINTING: 'Printing',
}

LOG = logging.getLogger(__name__)


class NotReady(Exception):
    pass


class Printer:
    def __init__(self, host, key, device, reconnect=False):
        self._host = host
        self._key = key
        self._device = device
        self._reconnect = reconnect
        self._state = {}
        self._condition = threading.Condition()
        self._sequence = 0
        if self._device:
            self.log = LOG.getChild(self._device)
        else:
            self.log = LOG

        self.client = mqtt.Client()
        self.client.enable_logger()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.username_pw_set('bblp', self._key)
        self.client.tls_set(cert_reqs=ssl.CERT_NONE)
        if reconnect:
            self.client.connect_async(host, 8883, 60)
        else:
            self.client.connect(host, 8883, 60)
        self.client.loop_start()

    @property
    def device(self):
        return self._device

    @property
    def state(self):
        return self._state

    @property
    def print_stage(self):
        try:
            return STAGES[int(self._state['mc_print_stage'])]
        except (KeyError, ValueError):
            return 'Stage %s' % self._state.get('mc_print_stage', 'Unknown')

    @property
    def task_name(self):
        return self._state.get('subtask_name', 'Unknown')

    @property
    def eta(self):
        try:
            eta = self._state['remain_eta']
        except KeyError:
            return '??:??'

        if eta.date() != datetime.date.today():
            return eta.strftime('%a %H:%M:%S')
        else:
            return eta.strftime('%H:%M:%S')

    def wait(self):
        with self._condition:
            self._condition.wait()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 5:
            client.loop_stop()
        elif rc != 0:
            self.log.warning("Connected with result code %i", rc)
        else:
            self.log.info('Connected to %s at %s',
                          self._device or 'printer', self._host)

        client.subscribe("#")

        try:
            self.pushall()
        except NotReady:
            pass

    def send(self, top, command, data):
        # We can only push stuff to the device if we know its ID
        if not self._device:
            raise NotReady()

        self._sequence += 1
        msg = {top: {'command': command, 'sequence_id': self._sequence}}
        msg[top].update(data)
        self.client.publish('device/%s/request' % self._device,
                            json.dumps(msg).encode() + b'\x00')

    def pushall(self):
        self.send('pushing', 'pushall', {'push_target': 1,
                                         'version': 1})

    def info(self):
        self.send('info', 'get_version', {})

    def _process_msg(self, client, userdata, msg):
        _device, printer, topic = msg.topic.split('/')

        if topic not in ('report', 'request'):
            self.log.info('Saw topic: %s' % msg.topic)
        if topic == 'request' and msg.payload.endswith(b'\x00'):
            data = msg.payload[:-1]
        else:
            data = msg.payload
        try:
            data = json.loads(data)
            if data:
                self.log.debug('%s: %s' % (topic, pprint.pformat(data)))
        except json.JSONDecodeError:
            self.log.warning('Non-JSON payload to %s: %r' % (msg.topic,
                                                             msg.payload))
            return

        if self._device is None and topic == 'report':
            self._device = printer
            self.log = LOG.getChild(self._device)
            if not self._state:
                self.pushall()
            self.log.info('Determined printer device ID to be %s',
                          self._device)

        if topic == 'report' and 'print' in data:
            return self._process_report_print(data)
        elif topic == 'report' and 'info' in data:
            self._process_report_info(data)

    def _process_report_info(self, data):
        data = data['info']
        if data['command'] == 'get_version':
            self._state['version'] = data['module']
        else:
            print('unknown %s')

    def _process_report_print(self, data):
        print_data = data.get('print', {})
        if not print_data:
            return

        if print_data.get('command') != 'push_status':
            self.log.debug('Unhandled command %r' % print_data.get('command'))
            return

        new_data = set()
        copy = ['mc_percent', 'mc_remaining_time', 'layer_num', 'wifi_signal',
                'mc_print_stage', 'mc_print_sub_stage', 'nozzle_temper',
                'chamber_temper', 'subtask_name']
        for k in copy:
            if k in print_data and print_data[k] != self._state.get(k):
                self._state[k] = print_data[k]
                new_data.add(k)

        if 'mc_remaining_time' in self._state:
            mins = self._state['mc_remaining_time']
            eta = datetime.datetime.now() + datetime.timedelta(minutes=mins)
            hours = mins / 60
            mins %= 60
            self._state.update({
                'remain_hr': hours,
                'remain_min': mins,
                'remain_eta': eta,
            })

        return new_data

    def on_message(self, client, userdata, msg):
        with self._condition:
            self._state['_last_changed'] = self._process_msg(
                client, userdata, msg)
            self._condition.notify()

    def on_disconnect(self, client, userdata, rc):
        reasons = {
            5: 'Unauthorized',
        }
        self.log.warning('Disconnected: %s',
                         reasons.get(rc, 'Unknown code %i' % rc))
        while self._reconnect:
            self.log.info('Reconnecting')
            try:
                self.client.reconnect()
            except (OSError, TimeoutError):
                continue
            else:
                break
        else:
            self._state['_connected'] = False

        with self._condition:
            self._condition.notify()
