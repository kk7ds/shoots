import datetime
import json
import ftplib
import logging
import pprint
import ssl
import threading

import paho.mqtt.client as mqtt

PRINT_STAGE_IDLE = 1
PRINT_STAGE_PRINTING = 2
# Also means filament ran out
PRINT_STAGE_PAUSED = 3
STAGES = {
    PRINT_STAGE_IDLE: 'Idle',
    PRINT_STAGE_PRINTING: 'Printing',
    PRINT_STAGE_PAUSED: 'Paused',
}

LOG = logging.getLogger(__name__)


class NotReady(Exception):
    pass


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass to support implicit FTPS.
    Constructor takes a boolean parameter ignore_PASV_host whether o ignore
    the hostname in the PASV response, and use the hostname from the session
    instead
    """
    def __init__(self, *args, **kwargs):
        self.ignore_PASV_host = kwargs.get('ignore_PASV_host') == True
        super().__init__(*args, {k: v for k, v in kwargs.items()
                                 if not k == 'ignore_PASV_host'})
        self._sock = None

    @property
    def sock(self):
        """Return the socket."""
        return self._sock

    @sock.setter
    def sock(self, value):
        """When modifying the socket, ensure that it is ssl wrapped."""
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        """Override the ntransfercmd method"""
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        conn = self.sock.context.wrap_socket(
            conn, server_hostname=self.host, session=self.sock.session
        )
        return conn, size

    def makepasv(self):
        host, port = super().makepasv()
        return (self.host if self.ignore_PASV_host else host), port


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
        self._ftp = None

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
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
    def key(self):
        return self._key

    @property
    def host(self):
        return self._host

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

    def print(self, **args):
        file = args.pop('file')
        default_args = {
            'param': 'Metadata/plate_1.gcode',
            'subtask_name': file,
            'url': 'ftp://%s' % file,
            'bed_type': 'auto',
            'timelapse': False,
            'bed_leveling': True,
            'flow_cali': False,
            'vibration_cali': True,
            'layer_inspect': True,
            'use_ams': True,
            'profile_id': '0',
            'project_id': '0',
            'subtask_id': '0',
            'task_id': '0',
        }
        default_args.update(args)
        self.send('print', 'project_file', default_args)

    def stop(self):
        self.send('print', 'stop', {'param': ''})

    def pause(self):
        self.send('print', 'pause', {'param': ''})

    def resume(self):
        self.send('print', 'resume', {'param': ''})

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

        self._state['print'] = print_data

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

    def connect_ftp(self):
        if not self._ftp:
            self._ftp = ImplicitFTP_TLS()
            self.log.debug('Connecting FTP to %s' % self.host)
            self._ftp.connect(self.host, port=990)
            self.log.debug('Logging into FTP with %s' % self.key)
            self._ftp.login('bblp', self.key)
            self.log.debug('Starting secure session')
            self._ftp.prot_p()
        return self._ftp
