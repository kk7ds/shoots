import argparse
import logging

from shoots import cli
from shoots import printer

LOG = logging.getLogger(__name__)


class Info(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        subparsers.add_parser('info', help='Show info about printer')

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        p.info()
        while 'version' not in p.state:
            LOG.debug('Waiting for version info')
            p.wait()

        print('Versions:')
        for module in p.state['version']:
            print('%(name)s: %(hw_ver)s %(sw_ver)s %(sn)s' % module)
