from pyengineio_client.exceptions import TransportError

from pyemitter import Emitter


class Transport(Emitter):
    def __init__(self, opts):
        self.hostname = opts['hostname']
        self.port = opts['port']
        self.secure = opts['secure']
        self.path = opts['path']
        self.query = opts['query']

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
        # TODO self.on_packet(parser.decode_packet(data, self.socket.binary_type))

    def on_packet(self, packet):
        """Called with a decoded packet."""
        self.emit('packet', packet)

    def on_close(self):
        """Called upon close."""
        self.ready_state = 'closed'
        self.emit('close')
