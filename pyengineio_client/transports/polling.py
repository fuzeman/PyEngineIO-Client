from .base import Transport

from threading import Semaphore
import pyengineio_parser as parser
import logging

log = logging.getLogger(__name__)


class Polling(Transport):
    name = "polling"

    protocol = 'http'
    protocol_secure = 'https'

    def __init__(self, opts):
        """Polling interface.

        :type opts: dict
        """
        super(Polling, self).__init__(opts)

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
        self.ready_state = 'pausing'

        def do_pause():
            log.debug('paused')
            self.ready_state = 'paused'
            on_pause()

        if self.polling or not self.writable:
            sem = Semaphore(int(self.polling) + int(not self.writable))

            def complete_pause():
                if not sem.acquire(blocking=False):
                    do_pause()

            if self.polling:
                log.debug('we are currently polling - waiting to pause')

                @self.once('pollComplete')
                def poll_complete():
                    log.debug('pre-pause polling complete')
                    sem.acquire(blocking=False)
                    complete_pause()

            if not self.writable:
                log.debug('we are currently writing - waiting to pause')

                @self.once('drain')
                def drain():
                    log.debug('pre-pause writing complete')
                    sem.acquire(blocking=False)
                    complete_pause()
        else:
            do_pause()

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
        log.debug('polling got data %s', repr(data))

        def callback(packet, index, total):
            # if its the first message we consider the transport open
            if self.ready_state == 'opening':
                self.on_open()

            # if its a close packet, we close the ongoing requests
            if packet['type'] == 'close':
                self.on_close()
                return

            # otherwise bypass onData and handle the message
            self.on_packet(packet)

        # decode payload
        parser.decode_payload(data, callback)

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
            self.write([{'type': 'close'}])

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

        def write_callback(data):
            self.writable = True
            self.emit('drain')

        parser.encode_payload(packets, lambda data: self.do_write(data, write_callback), self.supports_binary)

    def do_write(self, data, callback):
        raise NotImplementedError()
