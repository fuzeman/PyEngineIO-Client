from pyengineio_client.exceptions import TransportError
from pyengineio_client.util import qs_encode

from pyemitter import Emitter
import pyengineio_parser as parser
import time


class Transport(Emitter):
    name = None

    protocol = None
    protocol_secure = None

    def __init__(self, opts):
        self.hostname = opts['hostname']
        self.port = opts['port']
        self.secure = opts['secure']
        self.path = opts['path']
        self.query = opts['query']

        self.supports_binary = not (opts and opts.get('force_base64'))

        self.timestamp_param = opts['timestamp_param']
        self.timestamp_requests = opts['timestamp_requests']

        self.agent = opts['agent'] or False
        self.socket = opts['socket']

        self.ready_state = ''
        self.writable = False

    def on_error(self, message, desc=None):
        """Emits an error.

        :type message: str
        :type message: str
        :rtype: Transport
        """
        self.emit('error', TransportError(message, desc))
        return self

    def open(self):
        """Opens the transport."""
        if self.ready_state == 'closed' or self.ready_state == '':
            self.ready_state = 'opening'
            self.do_open()

        return self

    def do_open(self):
        raise NotImplementedError()

    def pause(self, on_pause):
        raise NotImplementedError()

    def close(self):
        """Closes the transport."""
        if self.ready_state == 'opening' or self.ready_state == 'open':
            self.do_close()
            self.on_close()

        return self

    def do_close(self):
        raise NotImplementedError()

    def send(self, packets):
        """Sends multiple packets.

        :type packets: list
        """
        if self.ready_state == 'open':
            self.write(packets)
        else:
            raise Exception('Transport not open')

    def write(self, packets):
        raise NotImplementedError()

    def on_open(self):
        """Called upon open"""
        self.ready_state = 'open'
        self.writable = True
        self.emit('open')

    def on_data(self, data):
        """Called with data

        :type data: str
        """
        self.on_packet(parser.decode_packet(data, self.socket.binary_type))

    def on_packet(self, packet):
        """Called with a decoded packet."""
        self.emit('packet', packet)

    def on_close(self):
        """Called upon close."""
        self.ready_state = 'closed'
        self.emit('close', 'transport closed')

    def uri(self):
        query = self.query or {}
        protocol = self.uri_protocol
        port = self.uri_port

        # add timestamp to query (if enabled)
        if self.timestamp_requests:
            query[self.timestamp_param] = int(time.time())

        # communicate binary support capabilities
        if not self.supports_binary:
            query['b64'] = 1

        query = qs_encode(query)

        # prepend ? to query
        if len(query):
            query = '?' + query

        return '%s://%s:%s%s%s' % (
            protocol, self.hostname, port,
            self.path, query
        )

    @property
    def uri_protocol(self):
        return self.protocol_secure if self.secure else self.protocol

    @property
    def uri_port(self):
        if not self.port:
            return ''

        # avoid port if default for schema
        if self.secure and self.port != 443:
            return self.port

        if not self.secure and self.port != 80:
            return self.port

        return ''
