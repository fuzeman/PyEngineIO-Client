from pyengineio_client.transports.polling import Polling
from pyengineio_client.transports.polling_jsonp import JSONP_Polling
from pyengineio_client.transports.polling_xhr import XHR_Polling
from pyengineio_client.transports.websocket import WebSocket

TRANSPORTS = {
    'polling': XHR_Polling,
    'websocket': WebSocket
}
