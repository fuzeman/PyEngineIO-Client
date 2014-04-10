from pyengineio_client.transports import TRANSPORTS
from pyengineio_client.url import parse_url
from pyengineio_client.util import qs_parse

from pyemitter import Emitter
import logging

log = logging.getLogger(__name__)



class Socket(Emitter):
    prior_websocket_success = False

    def __init__(self, uri, opts=None):
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

        self.transports = opts.get('transports') or ['polling-xhr', 'polling-jsonp', 'websocket']

        self.ready_state = ''
        self.write_buffer = []
        self.callback_buffer = []

        self.remember_upgrade = opts.get('remember_upgrade', False)

        self.binary_type = None
        self.only_binary_upgrades = opts.get('only_binary_upgrades')

        self.sid = None

        self.open()

    def create_transport(self, name):
        log.debug('creating transport "%s"', name)
        query = self.query.copy()

        # TODO append engine.io protocol identifier

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
        pass
