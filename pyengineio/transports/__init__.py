from pyengineio.transports.polling import Polling
from pyengineio.transports.polling_jsonp import JSONP_Polling
from pyengineio.transports.polling_xhr import XHR_Polling
from pyengineio.transports.websocket import WebSocket

TRANSPORTS = {
    'polling-jsonp': JSONP_Polling,
    'polling-xhr': XHR_Polling,
    'websocket': WebSocket
}
