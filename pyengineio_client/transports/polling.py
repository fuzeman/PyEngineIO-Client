from pyengineio_client.util import qs
from .base import Transport

import logging

log = logging.getLogger(__name__)


class Polling(Transport):
    name = "polling"

    def __init__(self, opts):
        """Polling interface.

        :type opts: dict
        """
        super(Polling, self).__init__(opts)

        self.supports_binary = not (opts and opts.get('force_base64'))

        self.polling = False

    def do_open(self):
        """Opens the socket (triggers polling). We write a PING message to determine
           when the transport is open.
        """
        self.poll()

    def pause(self, on_pause):
        """Pauses polling.

        :param on_pause: callback upon buffers are flushed and transport is paused
        :type on_pause: function
        """
        # TODO Polling.pause
        pass

    def poll(self):
        """Starts polling cycle."""
        log.debug('polling')
        self.polling = True
        self.do_poll()
        self.emit('poll')

    def do_poll(self):
        raise NotImplementedError()

    def on_data(self, data):
        """Overloads onData to detect payloads."""
        log.debug('polling got data %s', data)

        def callback(packet, index, total):
            # if its the first message we consider the transport open
            if self.ready_state == 'opening':
                self.on_open()

            # if its a close packet, we close the ongoing requests
            if packet.type == 'close':
                self.on_close()
                return

            # otherwise bypass onData and handle the message
            self.on_packet(packet)

        # decode payload
        # TODO parser.decodePayload(data, this.socket.binaryType, callback);

        # if an event did not trigger closing
        if self.ready_state != 'closed':
            # if we got data we're not polling
            self.polling = False
            self.emit('pollComplete')

            if self.ready_state == 'open':
                self.poll()
            else:
                log.debug('ignoring poll - transport state "%s"', self.ready_state)

    def do_close(self):
        """For polling, send a close packet."""
        def close():
            log.debug('writing close packet')
            self.write([{type: 'close'}])

        if self.ready_state == 'open':
            log.debug('transport open - closing')
            close()
        else:
            # in case we're trying to close while
            # handshaking is in progress (GH-164)
            log.debug('transport not open - deferring close')
            self.once('open', close)

    def write(self, packets):
        self.writable = False

        def callback():
            self.writable = True
            self.emit('drain')

        # TODO parser.encodePayload(packets, self.force_base64, lambda data: self.do_write(data, callback))

    def do_write(self, data, callback):
        raise NotImplementedError()

    def uri(self):
        query = self.query or {}
        schema = 'https' if self.secure else 'http'
        port = ''

        if not self.supports_binary and not query.sid:
            query['b64'] = 1

        query = qs(query)

        # avoid port if default for schema
        if self.port and (
            ('https' == schema and self.port != 443) or
            ('http' == schema and self.port != 80)
        ):
            port = ':%s' % self.port

        # prepend ? to query
        if len(query):
            query = '?' + query

        return schema + '://' + self.hostname + port + self.path + query
