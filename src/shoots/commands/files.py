import argparse
import ftplib
import logging
import os

from shoots import cli
from shoots import printer

LOG = logging.getLogger(__name__)


class Files(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('files', help='Manage files on printer')
        p.add_argument('subcommand', choices=['list', 'remove', 'get'])
        p.add_argument('--file', help='File or directory to act on')

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
        self._ftp = p.connect_ftp()
        if args.subcommand == 'list':
            return self.list(args, p)
        elif args.subcommand == 'remove':
            return self.remove(args, p)
        elif args.subcommand == 'get':
            return self.get(args, p)
        else:
            raise RuntimeError('Unknown command %s' % args.subcommand)
