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
        p.add_argument('subcommand', choices=['list', 'remove', 'get', 'put'])
        p.add_argument('file', nargs='?',
                       help='File or directory to act on')

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

    def remove(self, file):
        if not file:
            print('Must pass file to delete')
            return 1
        self._ftp.delete(file)

    def put(self, file):
        remotefn = os.path.basename(file)
        try:
            with open(file, 'rb') as f:
                self._ftp.storbinary('STOR %s' % remotefn, f)
        except OSError as e:
            print('Failed to read %s: %s' % (file, e))
            return 1
        print('Sent')

    def get(self, file):
        localfn = os.path.basename(file)
        if os.path.exists(localfn):
            print('File %r already exists, not overwriting' % file)
            return 1
        try:
            with open(localfn, 'wb') as f:
                self._ftp.retrbinary('RETR %s' % file, f.write)
        except OSError as e:
            print('Failed to write %s: %s' % (localfn, e))
        except ftplib.error_perm as e:
            print('Remote said: %s' % e)
            os.remove(localfn)
            return 1
        print('Fetched %s' % localfn)

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        self._ftp = p.connect_ftp()
        if args.subcommand in ['remove', 'put', 'get'] and not args.file:
            raise cli.UsageError('File is required for %s' % args.subcommand)

        if args.subcommand == 'list':
            return self.list(args, p)
        elif args.subcommand == 'remove':
            return self.remove(args.file)
        elif args.subcommand == 'put':
            return self.put(args.file)
        elif args.subcommand == 'get':
            return self.get(args.file)
        else:
            raise RuntimeError('Unknown command %s' % args.subcommand)
