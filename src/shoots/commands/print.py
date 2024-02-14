import argparse
import logging

from shoots import cli
from shoots import printer


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

    def execute(self, args:argparse.Namespace, p: printer.Printer):
        p.print(file=args.file,
                use_ams=not args.no_ams,
                bed_leveling=not args.no_level,
                flow_cali=not args.no_flowcal,
                timelapse=args.timelapse)
        p.wait()
