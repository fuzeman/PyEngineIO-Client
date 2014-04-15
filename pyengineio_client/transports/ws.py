from .base import Transport

from threading import Thread
import pyengineio_parser as parser
import logging
import websocket

log = logging.getLogger(__name__)


class WebSocket(Transport):
    name = "websocket"
    supports_binary = True

    protocol = 'ws'
    protocol_secure = 'wss'

    def __init__(self, opts):
        """WebSocket transport constructor.

        :param opts: connection options
        :type opts: dict
        """
        super(WebSocket, self).__init__(opts)

        self.thread = None
        self.ws = None

    def do_open(self):
        """Opens socket."""

        def ws_message(ws, data):
            log.debug('ws_message data: %s', repr(data))
            self.on_data(data)

        def ws_close(ws):
            log.debug('ws_close')
            self.on_close()

        websocket.enableTrace(True)

        self.ws = websocket.WebSocketApp(
            self.uri(),

            on_open=lambda ws: self.on_open(),
            on_message=ws_message,
            on_error=lambda ws, e: self.on_error(e.message),
            on_close=ws_close
        )

        self.thread = Thread(target=self.ws.run_forever)
        self.thread.start()

    def do_close(self):
        if self.ws:
            self.ws.close()

    def write(self, packets):
        self.writable = False

        # encodePacket efficient as it uses WS framing
        # no need for encodePayload
        for packet in packets:
            parser.encode_packet(packet, self.ws.send, self.supports_binary)

        # fake drain
        self.writable = True
        self.emit('drain')
