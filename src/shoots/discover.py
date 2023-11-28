import logging
import socket

LOG = logging.getLogger(__name__)


class UnableToDiscover(Exception):
    pass


def discover(args):
    """Find and return the first printer"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(10)
    try:
        sock.bind((args.listen, 2021))
    except OSError as e:
        raise UnableToDiscover('Unable to discover: %s' % str(e))
    r = sock.recv(1024)
    if r.startswith(b'NOTIFY *'):
        headers = dict(line.split(' ', 1)
                       for line in r.decode().split('\r\n') if line)
        LOG.debug('Found printer: %r' % headers)
        return {k[:-1]: v for k, v in headers.items()}
