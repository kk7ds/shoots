import argparse
import ftplib
import logging
import os
import ssl

from shoots import cli
from shoots import printer

LOG = logging.getLogger(__name__)


class ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass to support implicit FTPS.
    Constructor takes a boolean parameter ignore_PASV_host whether o ignore
    the hostname in the PASV response, and use the hostname from the session
    instead
    """
    def __init__(self, *args, **kwargs):
        self.ignore_PASV_host = kwargs.get('ignore_PASV_host') == True
        super().__init__(*args, {k: v for k, v in kwargs.items()
                                 if not k == 'ignore_PASV_host'})
        self._sock = None

    @property
    def sock(self):
        """Return the socket."""
        return self._sock

    @sock.setter
    def sock(self, value):
        """When modifying the socket, ensure that it is ssl wrapped."""
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        """Override the ntransfercmd method"""
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        conn = self.sock.context.wrap_socket(
            conn, server_hostname=self.host, session=self.sock.session
        )
        return conn, size

    def makepasv(self):
        host, port = super().makepasv()
        return (self.host if self.ignore_PASV_host else host), port


class Files(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('files', help='Manage files on printer')
        p.add_argument('subcommand', choices=['list', 'remove', 'get'])
        p.add_argument('--file', help='File or directory to act on')

    def _connect(self, args, p):
        self._ftp = ImplicitFTP_TLS()
        LOG.debug('Connecting FTP to %s' % p.host)
        self._ftp.connect(p.host, port=990)
        LOG.debug('Logging into FTP with %s' % p.key)
        self._ftp.login('bblp', p.key)
        LOG.debug('Starting secure session')
        self._ftp.prot_p()

    def list(self, args: argparse.Namespace, p: printer.Printer):
        if args.file:
            LOG.debug('Changing directory')
            self._ftp.cwd(args.file)
        LOG.debug('Listing')
        files = self._ftp.nlst()
        ignore = ['cache', 'ipcam', 'timelapse']
        for fn in files:
            try:
                sz = self._ftp.size(fn)
            except ftplib.error_perm:
                sz = 0
            units = 'B'
            if sz > 1024:
                sz /= 1024
                units = 'KiB'
            if sz > 1024:
                sz /= 1024
                units = 'MiB'
            if fn in ignore:
                continue
            print('%4i%-3s: %s' % (sz, units, fn))

    def remove(self, args: argparse.Namespace, p: printer.Printer):
        if not args.file:
            print('Must pass file to delete')
            return 1
        self._ftp.delete(args.file)

    def get(self, args: argparse.Namespace, p: printer.Printer):
        localfn = os.path.basename(args.file)
        if os.path.exists(localfn):
            print('File %r already exists, not overwriting' % args.file)
            return 1
        with open(localfn, 'wb') as f:
            self._ftp.retrbinary('RETR %s' % args.file, f.write)
        print('Fetched %s' % localfn)

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        self._connect(args, p)
        if args.subcommand == 'list':
            return self.list(args, p)
        elif args.subcommand == 'remove':
            return self.remove(args, p)
        elif args.subcommand == 'get':
            return self.get(args, p)
        else:
            raise RuntimeError('Unknown command %s' % args.subcommand)
