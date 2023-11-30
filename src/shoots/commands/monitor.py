import argparse

from shoots import cli
from shoots import printer


class Monitor(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        p = subparsers.add_parser('monitor', help='Watch printer status')
        p.add_argument('--until-finished', action='store_true', default=False,
                       help='Watch until print is complete')
        p.add_argument('--all-state', action='store_true', default=False,
                       help=('Dump all the (simple) state variables instead '
                             'of just the human-readable format'))
        p.add_argument('--one', action='store_true', default=False,
                       help='Query printer once and exit')

    def readable(self, p, state, changed):
        if {'mc_percent', 'mc_remaining_time', 'mc_print_stage'} & changed:
            print('%s %s %i%% complete %ih%im remaining, ETA %s' % (
                p.print_stage,
                p.print_stage == 'Printing' and p.task_name or 'stopped',
                state.get('mc_percent', 0),
                state.get('remain_hr', '?'),
                state.get('remain_min', '?'),
                p.eta))

    def all(self, state):
        print(','.join('%s=%r' % (k, v) for k, v in sorted(state.items())
                       if not isinstance(v, (list, dict))))

    def execute(self, args: argparse.Namespace, p: printer.Printer):
        while p.state.get('_connected') is not False:
            p.wait()
            state = p.state
            changed = state.get('_last_changed') or set()
            if args.all_state:
                self.all(state)
            else:
                self.readable(p, state, changed)

            if (state.get('mc_print_stage') == str(printer.PRINT_STAGE_IDLE)
                    and args.until_finished):
                return 0
            elif args.one:
                return 0
        return 255


class Debug(cli.ShootsCommand):
    def add_args(self, subparsers: argparse._SubParsersAction):
        subparsers.add_parser('debug', help='Watch for every stat')

    def execute(self, args, p):
        ignore = ('sequence_id',)
        ps = p.state.get('print', {})
        while True:
            p.wait()
            for k in ps.keys() | p.state.get('print', {}).keys():
                if k in ignore:
                    continue
                old = ps.get(k)
                new = p.state.get('print', {}).get(k)
                if new and old != new and not isinstance(new, (dict, list)):
                    print('%s: %r -> %r' % (k, old, new))
                    ps[k] = new
