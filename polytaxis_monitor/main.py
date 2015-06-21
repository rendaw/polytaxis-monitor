import os
import argparse
import signal
import time
import datetime

import watchdog
import watchdog.events
import watchdog.observers
import appdirs
import polytaxis

from polytaxis_monitor import common

verbose = False
super_verbose = False

die = False
def signal_handler(signal, frame):
    global die
    die = True
signal.signal(signal.SIGINT, signal_handler)

nextcommit = None
commit_wait = datetime.timedelta(seconds=5)

sleep_time = 5

log = print

def get_fid_and_raw_tags(parent, segment):
    got = cursor.execute(
        'SELECT id, tags FROM files WHERE parent is :parent AND segment = :segment LIMIT 1', 
        {
            'parent': parent, 
            'segment': segment,
        },
    ).fetchone()
    if got is None:
        return None, None
    return got[0], None if got[1] is None else got[1].encode('utf-8')

def get_fid(parent, segment):
    got = cursor.execute(
        'SELECT id FROM files WHERE parent is :parent AND segment = :segment LIMIT 1', 
        {
            'parent': parent, 
            'segment': segment,
        },
    ).fetchone()
    if got is None:
        return None
    return got[0]

def create_tree(splits, tags=None):
    fid = None
    last_index = len(splits) - 1
    for index, split in enumerate(splits):
        next_fid = get_fid(fid, split)
        if next_fid is None:
            args = {
                'parent': fid,
                'segment': split,
            }
            if tags and index == last_index:
                args['tags'] = polytaxis.encode_tags(tags).decode('utf-8')
            else:
                args['tags'] = None
            cursor.execute(
                'INSERT INTO files (id, parent, segment, tags) VALUES (NULL, :parent, :segment, :tags)',
                args,
            )
            next_fid = cursor.lastrowid
        fid = next_fid
    return fid

def create_file(filename, tags):
    if super_verbose:
        log('DEBUG: Created: [{}]'.format(filename))
    splits = common.split_abs_path(filename)
    return create_tree(splits, tags)

def update_file(fid, tags):
    cursor.execute(
        'UPDATE files SET tags = :tags WHERE id = :fid',
        {
            'fid': fid,
            'tags': polytaxis.encode_tags(tags).decode('utf-8'),
        },
    )

def clean_tree(fid):
    if cursor.execute(
            'SELECT count(1) FROM files WHERE parent is :id',
            {
                'id': fid,
            },
            ).fetchone()[0] > 0:
        return
    while fid is not None:
        parent = cursor.execute(
            'SELECT parent FROM files WHERE id is :id',
            {
                'id': fid,
            }
        ).fetchone()
        if parent is not None:
            (parent,) = parent
        cursor.execute('DELETE FROM files WHERE id is :id', {'id': fid})
        if cursor.execute(
                'SELECT count(1) FROM files WHERE parent is :id',
                {
                    'id': parent,
                },
                ).fetchone()[0] > 0:
            break
        fid = parent

def delete_file(fid):
    parent = cursor.execute(
        'SELECT parent FROM files WHERE id is :id',
        {
            'id': fid,
        }
    ).fetchone()
    if parent is not None:
        (parent,) = parent
    cursor.execute('DELETE FROM files WHERE id is :id', {'id': fid})
    clean_tree(parent)

def add_tags(fid, tags):
    for key, values in tags.items():
        for value in values:
            cursor.execute('INSERT INTO tags (tag, file) VALUES (:tag, :fid)',
                {
                    'tag': polytaxis.encode_tag(key, value).decode('utf-8'),
                    'fid': fid,
                }
            )

def remove_tags(fid):
    cursor.execute('DELETE FROM tags WHERE file = :fid', {'fid': fid})

def process(filename):
    filename = os.path.abspath(filename)
    if verbose:
        log('\tScanning file [{}]'.format(filename))
    is_file = os.path.isfile(filename)
    tags = polytaxis.get_tags(filename) if is_file else None
    if not tags and tags is not None:
        tags = {'untagged': set([None])}
    fid = None
    splits = common.split_abs_path(filename)
    last_split = splits.pop()
    for split in splits:
        fid = get_fid(fid, split)
        if fid is None:
            break
    fid, old_raw_tags = get_fid_and_raw_tags(fid, last_split)
    if tags is None and fid is None:
        if super_verbose:
            log('DEBUG: Not a file; skipping [{}]'.format(filename))
        pass
    elif tags is not None and fid is None:
        fid = create_file(filename, tags)
        add_tags(fid, tags)
    elif tags is not None and fid is not None:
        if super_verbose:
            log('DEBUG: Updating: [{}]'.format(filename))
        update_file(fid, tags)
        old_tags = polytaxis.decode_tags(old_raw_tags)
        if tags != old_tags:
            remove_tags(fid)
            add_tags(fid, tags)
    elif is_file and tags is None and fid is not None:
        if super_verbose:
            log('DEBUG: Deleted: [{}]'.format(filename))
        remove_tags(fid)
        delete_file(fid)

def move_file(source, dest):
    source = os.path.abspath(source)
    dest = os.path.abspath(dest)
    sparent = None
    sfid = None
    for split in common.split_abs_path(source):
        sparent = sfid
        sfid = get_fid(sparent, split)
        if sfid is None:
            process(dest)
            return
    dparent = None
    dfid = None
    dsplits = common.split_abs_path(dest)
    new_name = dsplits[-1]
    dsplits = dsplits[:-1]
    dfid = create_tree(dsplits)
    if super_verbose:
        log('DEBUG: Move {} -> {}'.format(source, dest))
    cursor.execute(
        'UPDATE files SET parent = :parent, segment = :segment WHERE id = :id',
        {
            'parent': dfid,
            'segment': new_name,
            'id': sfid,
        },
    )

class MonitorHandler(watchdog.events.FileSystemEventHandler):
    def _wait_or_commit(self):
        global nextcommit
        now = datetime.datetime.now()
        if nextcommit is not None and now >= nextcommit:
            conn.commit()
            if super_verbose:
                log('DEBUG: Committed')
            nextcommit = None
        else:
            nextcommit = now + commit_wait

    def on_created(self, event):
        if super_verbose:
            log('Event: create {}'.format(event.src_path))
        process(event.src_path)
        self._wait_or_commit()

    def on_deleted(self, event):
        if super_verbose:
            log('Event: delete {}'.format(event.src_path))
        process(event.src_path)
        self._wait_or_commit()

    def on_modified(self, event):
        if super_verbose:
            log('Event: modify {}'.format(event.src_path))
        process(event.src_path)
        self._wait_or_commit()

    def on_moved(self, event):
        if super_verbose:
            log('Event: move {} -> {}'.format(event.src_path, event.dest_path))
        move_file(event.src_path, event.dest_path)
        self._wait_or_commit()

def main():
    parser = argparse.ArgumentParser(
        description='Monitor directories, index polytaxis tags.',
    )
    parser.add_argument(
        'directory', 
        nargs='*',
        help='Path to monitor.', 
    )
    parser.add_argument(
        '-s',
        '--scan',
        action='store_true',
        help='Walk directories for missed file changes before monitoring.',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Enable verbose output.',
    )
    parser.add_argument(
        '-d',
        '--super_verbose',
        action='store_true',
        help='Enable very verbose output.',
    )
    args = parser.parse_args()

    if args.verbose or args.super_verbose:
        common.verbose = True
        global verbose
        verbose = True
    if args.super_verbose:
        global super_verbose
        super_verbose = True
    
    global cursor
    global conn
    conn, cursor = common.open_db()

    if args.scan:
        log('Looking for deleted files...')
        stack = [(False, None, None)]
        parts = []
        last_parent = None
        while stack:
            scanned, fid, segment = stack.pop()
            if not scanned:
                stack.append((True, fid, segment))
                if segment:
                    parts.append(segment)
                for next_segment, next_id in cursor.execute(
                        'SELECT segment, id FROM files WHERE parent is :parent',
                        {
                            'parent': fid,
                        }):
                    stack.append((False, next_id, next_segment))
            else:
                if parts:
                    joined = os.path.join(*parts)
                    if verbose:
                        log('Checking [{}]'.format(joined))
                    if joined and not os.path.exists(joined):
                        log('[{}] no longer exists, removing'.format(joined))
                        remove_tags(fid)
                        delete_file(fid)
                    parts.pop()

        for path in args.directory:
            log('Scanning [{}]...'.format(path))
            for base, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    abs_filename = os.path.join(base, filename)
                    process(abs_filename)

    conn.commit()

    if os.path.exists('/dev/shm'):
        tmpdir = '/dev/shm/polytaxis-monitor-{}/'.format(os.getpid())
    else:
        tmpdir = '/tmp/polytaxis-monitor-{}/'.format(os.getpid())
    os.makedirs(tmpdir, exist_ok=True)

    observer = watchdog.observers.Observer()
    handler = MonitorHandler()
    for path in args.directory:
        log('Starting watch on [{}]'.format(path))
        observer.schedule(handler, path, recursive=True)
    observer.schedule(handler, tmpdir, recursive=False)
    observer.start()
    try:
        while not die:
            time.sleep(sleep_time)
            if nextcommit and datetime.datetime.now() > nextcommit:
                with open(os.path.join(tmpdir, 'jostle'), 'w') as file:
                    file.write(repr(nextcommit))
    except KeyboardInterrupt:
        log('Received keyboard interrupt, please wait {} seconds'.format(
            sleep_time,
        ))
    observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
