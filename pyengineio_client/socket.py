from pyengineio_client.transports import TRANSPORTS
from pyengineio_client.url import parse_url
from pyengineio_client.util import qs_parse

from pyemitter import Emitter
from threading import Timer
import pyengineio_parser as parser
import json
import logging

log = logging.getLogger(__name__)


class Socket(Emitter):
    prior_websocket_success = False

    def __init__(self, uri, opts=None):
        """Socket constructor.

        :param uri: uri
        :type uri: str

        :param opts: options
        :type opts: dict
        """
        opts = opts or {}

        if uri:
            uri = parse_url(uri)
            opts['host'] = uri['host']
            opts['secure'] = uri['protocol'] in ['https', 'wss']
            opts['port'] = uri['port']

            if uri['query']:
                opts['query'] = uri['query']

        self.secure = opts.get('secure', False)
        self.agent = opts.get('agent') or False

        self.hostname = opts.get('host')
        self.port = opts.get('port') or (443 if self.secure else 80)

        self.query = opts.get('query') or {}
        if isinstance(self.query, basestring):
            self.query = qs_parse(self.query)

        self.upgrade = opts.get('upgrade', True)

        self.path = opts.get('path') or '/engine.io'
        if not self.path.endswith('/'):
            self.path += '/'

        self.force_jsonp = opts.get('force_jsonp', False)
        self.force_base64 = opts.get('force_base64', False)

        self.timestamp_param = opts.get('timestamp_param') or 't'
        self.timestamp_requests = opts.get('timestamp_requests')

        self.transports = opts.get('transports') or ['polling']

        self.ready_state = ''
        self.write_buffer = []
        self.callback_buffer = []

        self.remember_upgrade = opts.get('remember_upgrade', False)

        self.binary_type = None
        self.only_binary_upgrades = opts.get('only_binary_upgrades')

        self.sid = None
        self.transport = None
        self.upgrades = None

        self.ping_interval = None
        self.ping_interval_timer = None

        self.ping_timeout = None
        self.ping_timeout_timer = None

        self.upgrading = False

        self.write_buffer = []
        self.prev_buffer_len = 0

        self.open()

    def create_transport(self, name):
        """Creates transport of the given type.

        :param name: transport name
        :type name: str

        :rtype: Transport
        """
        log.debug('creating transport "%s"', name)
        query = self.query.copy()

        query['EIO'] = str(parser.PROTOCOL)

        # transport name
        query['transport'] = name

        # session id if we already have one
        if self.sid:
            query['sid'] = self.sid

        return TRANSPORTS[name]({
            'hostname': self.hostname,
            'port': self.port,
            'secure': self.secure,
            'path': self.path,
            'query': query,
            'force_jsonp': self.force_jsonp,
            'force_base64': self.force_base64,
            'timestamp_param': self.timestamp_param,
            'timestamp_requests': self.timestamp_requests,
            'agent': self.agent,
            'socket': self
        })

    def open(self):
        """Initializes transport to use and starts probe."""
        transport = None

        if self.remember_upgrade and self.prior_websocket_success and 'websocket' in self.transports:
            transport = 'websocket'
        else:
            transport = self.transports[0]

        self.ready_state = 'opening'

        transport = self.create_transport(transport)
        transport.open()

        self.set_transport(transport)

    def set_transport(self, transport):
        """Sets the current transport. Disables the existing one (if any)."""
        log.debug('setting transport %s', transport.name)

        if self.transport:
            log.debug('clearing existing transport %s', self.transport.name)
            self.transport.removeAllListeners()

        # set up transport
        self.transport = transport

        # set up transport listeners
        transport.on('drain', self.on_drain)\
                 .on('packet', self.on_packet)\
                 .on('error', self.on_error)\
                 .on('close', lambda: self.on_close('transport close'))

    def probe(self, name):
        """Probes a transport."""
        raise NotImplementedError()

    def on_open(self):
        """Called when connection is deemed open."""
        log.debug('socket open')
        self.ready_state = 'open'

        Socket.prior_websocket_success = 'websocket' == self.transport.name

        self.emit('open')
        # TODO this.onopen && this.onopen.call(this); ??
        self.flush()

        # we check for `readyState` in case an `open`
        # listener already closed the socket
        if self.ready_state == 'open' and self.upgrade and self.transport.pause:
            log.debug('starting upgrade probes')

            for upgrade in self.upgrades:
                self.probe(upgrade)

    def on_packet(self, packet):
        """Handles a packet."""
        if self.ready_state in ['opening', 'open']:
            log.debug('socket receive: type "%s", data "%s"', packet.get('type'), packet.get('data'))

            self.emit('packet', packet)

            # Socket is live - any packet counts
            self.emit('heartbeat')

            p_type = packet.get('type')
            p_data = packet.get('data')

            if p_type == 'open':
                return self.on_handshake(json.loads(p_data))

            if p_type == 'pong':
                return self.set_ping()

            if p_type == 'error':
                return self.emit('error', Exception('server error', p_data))

            if p_type == 'message':
                self.emit('data', p_data)
                self.emit('message', p_data)

                # TODO this.onmessage && this.onmessage.call(this, event);
                return

        else:
            log.debug('packet received with socket ready_state "%s"', self.ready_state)

    def on_handshake(self, data):
        """Called upon handshake completion."""
        self.emit('handshake', data)

        self.sid = data.get('sid')
        self.transport.query['sid'] = self.sid

        self.upgrades = self.filter_upgrades(data.get('upgrades'))

        self.ping_interval = data.get('pingInterval')
        self.ping_timeout = data.get('pingTimeout')

        self.on_open()
        self.set_ping()

        # Prolong liveness of socket on heartbeat
        self.off('heartbeat', self.on_heartbeat)
        self.on('heartbeat', self.on_heartbeat)

    def on_heartbeat(self, timeout=None):
        """Resets ping timeout."""
        if self.ping_timeout_timer:
            self.ping_timeout_timer.cancel()

        def timer_callback():
            if self.ready_state == 'closed':
                return

            self.on_close('ping timeout')

        if not timeout:
            timeout = self.ping_interval + self.ping_timeout

        log.debug("ping_timeout_timer updated, timeout: %s" % timeout)

        self.ping_timeout_timer = Timer(timeout / 1000, timer_callback)
        self.ping_timeout_timer.start()

    def set_ping(self):
        """Pings server every `self.ping_interval` and expects response
           within `self.ping_timeout` or closes connection."""
        if self.ping_interval_timer:
            self.ping_interval_timer.cancel()

        def timer_callback():
            log.debug('writing ping packet - expecting pong within %sms', self.ping_timeout)
            self.ping()
            self.on_heartbeat(self.ping_timeout)

        log.debug("ping_interval_timer updated, interval: %s" % self.ping_interval)

        self.ping_interval_timer = Timer(self.ping_interval / 1000, timer_callback)
        self.ping_interval_timer.start()

    def ping(self):
        """Sends a ping packet."""
        self.send_packet('ping')

    def on_drain(self):
        """Called on `drain` event"""
        for x in range(self.prev_buffer_len):
            if not self.callback_buffer[x]:
                continue

            self.callback_buffer[x]()

        self.write_buffer = self.write_buffer[self.prev_buffer_len:]
        self.callback_buffer = self.callback_buffer[self.prev_buffer_len:]

        # setting prevBufferLen = 0 is very important
        # for example, when upgrading, upgrade packet is sent over,
        # and a nonzero prevBufferLen could cause problems on `drain`
        self.prev_buffer_len = 0

        if not self.write_buffer:
            self.emit('drain')
        else:
            self.flush()

    def flush(self):
        """Flush write buffers."""
        if self.ready_state == 'closed' or self.upgrading:
            return

        if not self.transport.writable or not self.write_buffer:
            return

        log.debug('flushing %d packets in socket', len(self.write_buffer))
        self.transport.send(self.write_buffer)

        # keep track of current length of writeBuffer
        # splice writeBuffer and callbackBuffer on `drain`
        self.prev_buffer_len = len(self.write_buffer)

        self.emit('flush')

    def write(self, message, callback=None):
        """Sends a message.

        :param message: message
        :type message: str

        :param callback: callback function for response
        :type callback: function
        """
        self.send_packet('message', message, callback)
        return self

    def send_packet(self, p_type, data=None, callback=None):
        """Sends a packet.

        :param p_type: packet type.
        :type p_type: str

        :param data: packet data.
        :type data: str

        :param callback: callback function for response
        :type callback: function
        """
        packet = {'type': p_type, 'data': data}
        self.emit('packetCreate', packet)

        self.write_buffer.append(packet)
        self.callback_buffer.append(callback)

        self.flush()

    def close(self):
        """Closes the connection"""
        raise NotImplementedError()

    def on_error(self, message):
        """Called upon transport error"""
        log.debug('socket error %s', message)
        Socket.prior_websocket_success = False

        self.emit('error', message)
        # TODO this.onerror && this.onerror.call(this, err) ??

        self.on_close('transport error  %s' % message)

    def on_close(self, reason, desc=None):
        """Called upon transport close"""
        if self.ready_state not in ['opening', 'open']:
            return

        log.debug('socket close with reason: "%s"', reason)

        # Clear ping interval timer
        if self.ping_interval_timer:
            self.ping_interval_timer.cancel()

        self.ping_interval_timer = None

        # Clear ping timeout timer
        if self.ping_timeout_timer:
            self.ping_timeout_timer.cancel()

        self.ping_timeout_timer = None

        # ensure transport won't stay open
        self.transport.close()

        # ignore further transport communication
        self.transport.off()

        # set ready state
        self.ready_state = 'closed'

        # clear session id
        self.sid = None

        # emit close event
        self.emit('close', reason, desc)

        # clean buffers after the `close` emit, so developers
        # can still grab the buffers
        self.write_buffer = []
        self.callback_buffer = []
        self.prev_buffer_len = 0

    def filter_upgrades(self, upgrades):
        """Filters upgrades, returning only those matching client transports.

        :param upgrades: server upgrades
        :type upgrades: list
        """
        return [u for u in upgrades if u in self.transports]
