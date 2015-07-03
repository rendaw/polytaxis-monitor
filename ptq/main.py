import argparse
import sys
import os
import signal

import appdirs

import polytaxis_monitor.common
import polytaxis_monitor.main

def limit(maxcount, generator):
    count = 0
    for x in generator:
        if count >= maxcount:
            break
        count += 1
        yield x


def reverse(args):
    conn, cursor = polytaxis_monitor.common.open_db()  
    setattr(polytaxis_monitor.main, 'conn', conn)
    setattr(polytaxis_monitor.main, 'cursor', cursor)

    if args.add:
        for file in args.files:
            polytaxis_monitor.main.process(file)
    else:
        for file in args.files:
            print(file)
            fid, raw_tags = polytaxis_monitor.main.locate(file)
            if fid is None:
                print('[{}] not in database.'.format(file))
                return 1
            print('id: {}'.format(fid))
            print('raw_tags: {}'.format(repr(raw_tags)))
            print('tag entries: {}'.format(
                cursor.execute('SELECT * FROM tags WHERE file = :fid', {'fid': fid}).fetchall()
            ))
            print('')
    return 0


def forward(args):
    if args.unwrap:
        unwrap_root = os.path.join(
            appdirs.user_data_dir('polytaxis-unwrap', 'zarbosoft'),
            'mount',
        )

    db = polytaxis_monitor.common.QueryDB()

    if args.tags:
        if len(args.args) > 1:
            parser.error(
                'When querying tags you may specify at most one query argument.'
            )
        rows = [
            row for row in limit(
                args.limit, db.query_tags(
                    args.tags, 
                    args.args[0] if args.args else ''
                )
            )
        ]
        for row in rows:
            print(row)
    else:
        includes, excludes, filters, sort, columns = (
            polytaxis_monitor.common.parse_query(args.args)
        )
        rows = list(limit(
            args.limit, 
            polytaxis_monitor.common.filter(
                filters,
                db.query(includes, excludes),
            ),
        ))
        rows = polytaxis_monitor.common.sort(sort, rows)
        for row in rows:
            if args.columns:
                text = '\t'.join(
                    ','.join(list(row['tags'].get(column, []))) 
                    for column in columns
                )
                if args.print0:
                    sys.stdout.write(path)
                    sys.stdout.write('\x00')
                else:
                    print(text)
            else:
                path = db.query_path(row['fid'])
                if len(path) >= 2 and path[1] == ':':
                    path = path[2:]
                if args.unwrap:
                    path = path[1:]
                    path = os.path.join(unwrap_root, path)
                if args.print0:
                    sys.stdout.write(path)
                    sys.stdout.write('\x00')
                else:
                    print(path)
    if not args.print0 and len(rows) == args.limit:
        sys.stderr.write('Stoped at {} results.\n'.format(args.limit))


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    if (
            not any(key in sys.argv for key in ('-h', '--help')) and
            len(sys.argv) < 2 or sys.argv[1] not in ('forward', 'reverse')
            ):
        sys.argv.insert(1, 'forward')

    parser = argparse.ArgumentParser(
        description='Query files and tags in the polytaxis_monitor database.',
    )
    commands = parser.add_subparsers(dest='command')

    def add_common_subparser(*pargs, **kwargs):
        out = commands.add_parser(*pargs, **kwargs)
        out.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            help='Enable verbose output.',
        )
        out.add_argument(
            '-d',
            '--super_verbose',
            action='store_true',
            help='Enable very verbose output.',
        )
        return out

    query_command = add_common_subparser('forward', description='Query the database.')
    query_command.add_argument(
        'args',
        help='Query argument(s).',
        nargs='+',
        default=[],
    )
    query_command.add_argument(
        '-t',
        '--tags',
        help='Query tags rather than files.',
        choices=['prefix', 'anywhere'],
        nargs='?',
        const='prefix',
    )
    query_command.add_argument(
        '-n',
        '--limit',
        help='Limit number of results.',
        type=int,
        default=1000,
    )
    query_command.add_argument(
        '-u',
        '--unwrap',
        help='Provide polytaxis-unwrap\'ed filename results. polytaxis-unwrap must be running.',
        action='store_true',
    )
    query_command.add_argument(
        '-0',
        '--print0',
        help='Separate filenames with null characters (0x00) rather than newlines.',
        action='store_true',
    )
    query_command.add_argument(
        '-c',
        '--columns',
        help='Display columns rather than file paths.',
        action='store_true',
    )

    reverse_command = add_common_subparser('reverse', description='Reverse query the database.')
    reverse_command.add_argument(
        'files',
        help='File(s) to check.',
        nargs='+',
        default=[],
    )
    reverse_command.add_argument(
        '-a',
        '--add',
        help='Add a file to the database if it is missing.',
        action='store_true',
    )

    args = parser.parse_args()

    if args.verbose or args.super_verbose:
        polytaxis_monitor.common.verbose = True
        setattr(polytaxis_monitor.main, 'verbose', True)
    if args.super_verbose:
        setattr(polytaxis_monitor.main, 'super_verbose', True)

    if args.command == 'reverse':
        return reverse(args)
    else:
        return forward(args)


if __name__ == '__main__':
    sys.exit(main())
