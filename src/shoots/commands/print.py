import argparse
import logging
import os

from shoots import cli
from shoots import printer

LOG = logging.getLogger(__name__)


class Print(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('print', help='Control printing')
        p.add_argument('file', help='File to print')
        p.add_argument('--no-ams', action='store_true', default=False,
                       help='Do not use AMS')
        p.add_argument('--no-level', action='store_true', default=False,
                       help='Do not level bed')
        p.add_argument('--no-flowcal', action='store_true', default=False,
                       help='Do not flow calibrate')
        p.add_argument('--timelapse', action='store_true', default=False,
                       help='Record timelapse')
        p.add_argument('--upload', help='Upload this file and then print it')

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        if args.upload:
            remote_file = os.path.basename(args.file)
            ftp = p.connect_ftp()
            LOG.info('Uploading %s to %s', args.file, remote_file)
            with open(args.file, 'rb') as f:
                ftp.storbinary('STOR %s' % remote_file, f.read)
            LOG.info('Uploaded')
        else:
            remote_file = args.file

        p.print(file=remote_file,
                use_ams=not args.no_ams,
                bed_leveling=not args.no_level,
                flow_cali=not args.no_flowcal,
                timelapse=args.timelapse)
        p.wait()
