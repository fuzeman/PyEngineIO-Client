from .polling import Polling

from requests_futures.sessions import FuturesSession
import logging

log = logging.getLogger(__name__)


class XHR_Polling(Polling):
    def __init__(self, opts):
        super(XHR_Polling, self).__init__(opts)

        self.supports_binary = True

        self.session = FuturesSession()

    def request(self, data=None, method='GET', callback=None):
        future = None

        if method == 'GET':
            future = self.session.get(self.uri())
        elif method == 'POST':
            future = self.session.post(
                self.uri(), data,

                # Important for binary requests
                headers={'Content-Type': 'application/octet-stream'}
            )
        else:
            self.on_error('Unknown method specified')

        def on_response(future):
            if not future.done():
                exc = future.exception()
                self.on_error(exc.message)
                return

            response = future.result()

            if response.status_code != 200:
                self.on_error('request returned with status code %s' % response.status_code)
                return

            if callback:
                callback(bytearray(response.content))

        future.add_done_callback(on_response)

    def do_write(self, data, callback):
        """Sends data.

        :param data: data to send
        :type data: str

        :param callback: called upon flush
        :type callback: function
        """
        self.request(
            data=data,
            method='POST',
            callback=callback
        )

    def do_poll(self):
        log.debug('xhr poll')
        self.request(callback=self.on_data)
