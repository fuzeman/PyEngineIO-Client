from pyengineio_client.socket import Socket


def connect(uri, opts=None):
    if opts is None:
        opts = {}

    return Socket(uri, opts)
