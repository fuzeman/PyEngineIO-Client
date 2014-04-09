class TransportError(Exception):
    def __init__(self, message, desc):
        super(TransportError, self).__init__(message, desc)
