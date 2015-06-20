import argparse
import sys
import os
import signal

import appdirs

import polytaxis_monitor.common

def limit(maxcount, generator):
    count = 0
    for x in generator:
        if count >= maxcount:
            break
        count += 1
        yield x

def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    parser = argparse.ArgumentParser(
        description='Query files and tags in the polytaxis_monitor database.',
    )
    parser.add_argument(
        'args',
        help='Query argument(s).',
        nargs='*',
        default=[],
    )
    parser.add_argument(
        '-t',
        '--tags',
        help='Query tags rather than files.',
        choices=['prefix', 'anywhere'],
        nargs='?',
        const='prefix',
    )
    parser.add_argument(
        '-n',
        '--limit',
        help='Limit number of results.',
        type=int,
        default=1000,
    )
    parser.add_argument(
        '-u',
        '--unwrap',
        help='Provide polytaxis-unwrap\'ed filename results. polytaxis-unwrap must be running.',
        action='store_true',
    )
    parser.add_argument(
        '-0',
        '--print0',
        help='Separate filenames with null characters (0x00) rather than newlines.',
        action='store_true',
    )
    parser.add_argument(
        '-c',
        '--columns',
        help='Display columns rather than file paths.',
        action='store_true',
    )
    args = parser.parse_args()

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

if __name__ == '__main__':
    main()
