import errno
import os
import sqlite3
import functools
import random
import hashlib
import operator
import ntpath

import appdirs
import polytaxis
import natsort

verbose = False

_natkey = natsort.natsort_keygen()


def os_path_split_asunder(path, windows):
    # Thanks http://stackoverflow.com/questions/4579908/cross-platform-splitting-of-path-in-python/4580931#4580931
    # Mod for windows paths on linux
    parts = []
    while True:
        newpath, tail = (ntpath.split if windows else os.path.split)(path)
        if newpath == path:
            assert not tail
            if path: parts.append(path)
            break
        parts.append(tail)
        path = newpath
    parts.reverse()
    return parts


def split_abs_path(path):
    windows = False
    out = []
    if len(path) > 1 and path[1] == ':':
        windows = True
        drive, path = ntpath.splitdrive(path)
        out.append(drive)
    extend = os_path_split_asunder(path, windows)
    if windows:
        extend.pop(0)
    out.extend(extend)
    return out


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise


def init_db(cursor):
    cursor.execute('CREATE TABLE files (id INTEGER PRIMARY KEY, parent INT, segment TEXT NOT NULL, tags TEXT)')
    cursor.execute('CREATE TABLE tags (tag TEXT NOT NULL, file INT NOT NULL)')


def open_db():
    root = appdirs.user_data_dir('polytaxis-monitor', 'zarbosoft')
    mkdir_p(root)

    db_path = os.path.join(root, 'db.sqlite3')
    do_init_db = False
    if not os.path.exists(db_path):
        print('Initializing db at [{}]'.format(db_path))
        do_init_db = True
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    if do_init_db:
        init_db(cursor)
    return conn, cursor


def _shifttext(source, match):
    if not source.startswith(match):
        return None
    return source[len(match):]


def parse_query(args):
    includes = set()
    excludes = set()
    filters = set()
    columns = []
    sort = []
    for item in args:
        col = _shifttext(item, 'col:')
        if col:
            columns.append(col)
            continue
        sort_asc = _shifttext(item, 'sort+:')
        if sort_asc:
            if sort_desc not in columns:
                columns.append(sort_asc)
            sort.append(('asc', sort_asc))
            continue
        sort_desc = _shifttext(item, 'sort-:')
        if sort_desc:
            if sort_desc not in columns:
                columns.append(sort_desc)
            sort.append(('desc', sort_desc))
            continue
        sort_rand = _shifttext(item, 'sort?:')
        if sort_rand:
            if sort_rand not in columns:
                columns.append(sort_rand)
            sort.append(('rand', sort_rand))
            continue
        exclude = _shifttext(item, '^')
        if exclude:
            excludes.add(exclude)
            continue
        ritem = item[::-1]
        equal_at = ritem.find('=')
        if -1 < ritem.find('=>') >= equal_at:
            splits = item.split('>=', 2)
            includes.add('{}=%'.format(splits[0]))
            filters.add((operator.ge, splits[0], splits[1]))
            if splits[0] not in columns:
                columns.append(splits[0])
            continue
        if -1 < ritem.find('>') >= equal_at:
            splits = item.split('>', 2)
            includes.add('{}=%'.format(splits[0]))
            filters.add((operator.gt, splits[0], splits[1]))
            if splits[0] not in columns:
                columns.append(splits[0])
            continue
        if -1 < ritem.find('=<') >= equal_at:
            splits = item.split('<=', 2)
            includes.add('{}=%'.format(splits[0]))
            filters.add((operator.le, splits[0], splits[1]))
            if splits[0] not in columns:
                columns.append(splits[0])
            continue
        if -1 < ritem.find('<') >= equal_at:
            splits = item.split('<', 2)
            includes.add('{}=%'.format(splits[0]))
            filters.add((operator.lt, splits[0], splits[1]))
            if splits[0] not in columns:
                columns.append(splits[0])
            continue
        includes.add(item)
    return includes, excludes, filters, sort, columns


class QueryDB(object):
    def __init__(self):
        conn, self.cursor = open_db()

    def clear_cache(self):
        self._query_path_element.cache_clear()

    @functools.lru_cache()
    def _query_path_element(self, fid):
        return self.cursor.execute(
            'SELECT parent, segment FROM files WHERE id = :id LIMIT 1',
            {
                'id': fid,
            },
        ).fetchone()

    def query_path(self, fid):
        segments = []
        while fid is not None:
            fid, segment = self._query_path_element(fid)
            segments.append(segment)
        return os.path.join(*reversed(segments))

    def query(self, include, exclude, add_path=False):
        # Assemble includes/excludes into a sql query
        query_include = []
        query_exclude = []
        query_args = {
        }
        query_index = [0]

        def build_select(dest, item):
            if '%' in item:
                dest.append(
                    'SELECT file FROM tags WHERE tag LIKE :tag{}'.format(
                        query_index[0]
                    )
                )
            else:
                dest.append(
                    'SELECT file FROM tags WHERE tag = :tag{}'.format(
                        query_index[0]
                    )
                )
            query_args['tag{}'.format(query_index[0])] = item
            query_index[0] += 1

        for item in include:
            build_select(query_include, item)

        if len(query_include) == 0:
            query_include.append('SELECT file FROM tags')

        for item in exclude:
            build_select(query_exclude, item)

        if query_index[0] == 0:
            query_select = 'SELECT id FROM files WHERE tags is not NULL LIMIT :size OFFSET :offset'
        else:
            if query_include:
                query_exclude.insert(0, ' INTERSECT '.join(query_include))
            query_select = (
                ' EXCEPT '.join(query_exclude) + ' LIMIT :size OFFSET :offset'
            )
        
        # Perform the query in batches, and manually apply the rest of the
        # filtering.
        batch_size = 100
        batch_index = 0
        while True:
            query_args['offset'] = batch_index * batch_size
            query_args['size'] = batch_size
            batch = set(
                self.cursor.execute(query_select, query_args).fetchall()
            )
            batch_index += 1
            for (fid,) in batch:
                segment, tags = self.cursor.execute(
                    'SELECT segment, tags FROM files WHERE id = :fid LIMIT 1',
                    {
                        'fid': fid,
                    },
                ).fetchone()
                tags = polytaxis.decode_tags(tags.encode('utf-8'))
                out = {
                    'fid': fid,
                    'segment': segment,
                    'tags': tags,
                }
                if add_path:
                    out['tags']['path'] = {self.query_path(fid)}
                yield out
            if len(batch) < batch_size:
                break

    def query_tags(self, method, arg):
        batch_size = 100
        batch_index = 0
        while True:
            if method == 'prefix':
                batch = self.cursor.execute(
                    'SELECT DISTINCT tag FROM tags WHERE tag LIKE :arg ORDER BY tag ASC LIMIT :size OFFSET :offset',
                    {
                        'arg': arg + '%',
                        'offset': batch_index * batch_size,
                        'size': batch_size,
                    },
                ).fetchall()
            elif method == 'anywhere':
                batch = self.cursor.execute(
                    'SELECT DISTINCT tag FROM tags WHERE tag LIKE :arg ORDER BY tag ASC LIMIT :size OFFSET :offset',
                    {
                        'arg': '%' + arg + '%',
                        'offset': batch_index * batch_size,
                        'size': batch_size,
                    },
                ).fetchall()
            batch_index += 1 
            for (tag,) in batch:
                yield tag
            if len(batch) < batch_size:
                break


def _get(row, column):
    row_val = row['tags'].get(column)
    return next(iter(row_val)) if row_val is not None else ''


def filter(filters, rows):
    filters = [
        (comp, key, _natkey(val)) for comp, key, val in filters
    ]
    for row in rows:
        filtered = False
        for comp, key, val in filters:
            if not comp(_natkey(_get(row, key)), val):
                filtered = True
                break
        if filtered:
            continue
        yield row


def sort(sort_info, rows):
    salt = '{:03d}'.format(random.randint(0, 999)).encode('utf-8')
    random.shuffle(rows)
    def cmp(x, y):
        for direction, column in sort_info:
            x_val = _get(x, column)
            y_val = _get(y, column)
            if direction == 'rand':
                x_val = hashlib.md5(x_val.encode('utf-8') + salt).digest()
                y_val = hashlib.md5(y_val.encode('utf-8') + salt).digest()
            else:
                x_val = _natkey(x_val)
                y_val = _natkey(y_val)
            less = 0
            if y_val is None:
                less = 1
            elif x_val < y_val:
                less = -1
            elif x_val > y_val:
                less = 1
            if less == 0:
                continue
            if direction == 'desc':
                return less * -1
            else:
                return less
        return 0
    return sorted(rows, key=functools.cmp_to_key(cmp))

