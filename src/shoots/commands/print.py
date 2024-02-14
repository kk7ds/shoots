import argparse
import logging
import os

from shoots import cli
from shoots import printer

LOG = logging.getLogger(__name__)


class Print(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('print', help='Control printing')
        p.add_argument('file', nargs='?', help='File to print')
        p.add_argument('--stop', action='store_true',
                       help='Stop an in-progress print')
        p.add_argument('--pause', action='store_true',
                       help='Pause an in-progress print')
        p.add_argument('--resume', action='store_true',
                       help='resume an in-progress print')
        p.add_argument('--ams-slot', type=int, default=None,
                       help='Use this AMS slot')
        p.add_argument('--plate', choices=['textured_plate',
                                           'eng_plate',
                                           'cool_plate',
                                           'hot_plate'],
                       default='auto',
                       help='Which plate to use')
        p.add_argument('--no-level', action='store_true', default=False,
                       help='Do not level bed')
        p.add_argument('--no-flowcal', action='store_true', default=False,
                       help='Do not flow calibrate')
        p.add_argument('--timelapse', action='store_true', default=False,
                       help='Record timelapse')
        p.add_argument('--upload', action='store_true',
                       help='Upload the file and then print it')

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        if args.stop:
            p.stop()
            p.wait()
            return
        elif args.pause:
            p.pause()
            p.wait()
            return
        elif args.resume:
            p.resume()
            p.wait()
            return

        if not args.file:
            raise cli.UsageError('File is required')
            return 1

        if args.upload:
            remote_file = os.path.basename(args.file)
            ftp = p.connect_ftp()
            LOG.info('Uploading %s to %s', args.file, remote_file)
            with open(args.file, 'rb') as f:
                ftp.storbinary('STOR %s' % remote_file, f)
            LOG.info('Uploaded')
        else:
            remote_file = args.file

        ams_args = {'use_ams': False}
        if args.ams_slot:
            ams_args['use_ams'] = True
            ams_args['ams_mapping'] = [args.ams_slot - 1]

        p.print(file=remote_file,
                bed_leveling=not args.no_level,
                flow_cali=not args.no_flowcal,
                timelapse=args.timelapse,
                bed_type=args.plate,
                **ams_args)
        p.wait()
