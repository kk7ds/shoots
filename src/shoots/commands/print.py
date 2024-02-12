import argparse
import logging

from shoots import cli
from shoots import printer


class Print(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('print', help='Control printing')
        p.add_argument('subcommand', choices=['fromsd'])
        p.add_argument('--file', help='File to act on')

    def execute(self, args:argparse.Namespace, p: printer.Printer):
        if args.subcommand == 'fromsd':
            p.print(file=args.file)
        p.wait()
