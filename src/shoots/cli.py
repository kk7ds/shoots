import argparse
import logging
import pkg_resources

from shoots import discover
from shoots import printer

LOG = logging.getLogger(__name__)


# This is the base class you inherit from to add a new command
class ShootsCommand:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    # Called to add sub-parser arguments to the parser
    def add_args(self, subparsers: argparse._SubParsersAction):
        pass

    # Called to run the command, returns exit code for shell
    def execute(self, args: argparse.Namespace, printer: printer.Printer):
        pass


def main():
    commands = {}

    p = argparse.ArgumentParser()
    p.add_argument('key', help='Network key')
    sp = p.add_subparsers(dest='command',
                          help='Command to run')
    p.add_argument('--host', help=('Hostname to connect to, '
                                   'otherwise find first printer via '
                                   'discovery'))
    p.add_argument('--device', help=('Printer Device ID (detect on connect if '
                                     'ommitted)'))
    p.add_argument('--listen', default='0.0.0.0',
                   help='Listen address for discovery')
    p.add_argument('--reconnect', action='store_true', default=False,
                   help='Attempt to (re)connect forever')
    p.add_argument('-v', '--verbose', action='store_true', default=False,
                   help='Log verbosely')
    p.add_argument('--debug', action='store_true', default=False,
                   help='Log all messages and other debug info')

    for entry_point in pkg_resources.iter_entry_points('shoots'):
        command = entry_point.load()(entry_point.name)
        command.add_args(sp)
        commands[entry_point.name] = command

    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else
                        logging.INFO if args.verbose else logging.WARNING)

    if not args.host:
        try:
            printer_data = discover.discover(args)
        except discover.UnableToDiscover as e:
            print(e)
            return 1
        args.host = printer_data['Location']
        args.device = printer_data['USN']
        if not args.host:
            print('No printer found via discovery')
            return 1
        else:
            LOG.info('Found printer %s (%s) via discovery at %s' % (
                printer_data['DevName.bambu.com'],
                args.device,
                args.host))

    try:
        p = printer.Printer(args.host, args.key, args.device,
                            reconnect=args.reconnect)
    except OSError as e:
        print('Failed to connect to %s: %s' % (args.host, e))
        return 1

    try:
        command = commands[args.command]
        return command.execute(args, p)
    except KeyboardInterrupt:
        p.client.disconnect()
