import unittest
import sqlite3
import operator

from mock import patch

import polytaxis_monitor.common
import polytaxis_monitor.main

db = sqlite3.connect(':memory:')
db_cursor = db.cursor()
polytaxis_monitor.common.init_db(db)
polytaxis_monitor.main.conn = db
polytaxis_monitor.main.cursor = db_cursor

class TestWrite(unittest.TestCase):
    def setUp(self):
        db.execute('DELETE FROM tags')
        db.execute('DELETE FROM files')

    def test_split_abs_path(self):
        self.assertEqual(
            list(polytaxis_monitor.common.split_abs_path('/a/b/c.txt')),
            ['/', 'a', 'b', 'c.txt'],
        )
    
    def test_split_abs_path_win(self):
        self.assertEqual(
            list(polytaxis_monitor.common.split_abs_path('c:\\a\\b\\c.txt')),
            ['c:', 'a', 'b', 'c.txt'],
        )

    def test_create_file(self):
        tags = {'a': set(['b'])}
        fid = polytaxis_monitor.main.create_file(
            '/what/you/at/gamma.vob', 
            tags,
        )
        polytaxis_monitor.main.add_tags(fid, tags)
        self.assertEqual(
            db.execute('SELECT * FROM files').fetchall(),
            [
                (1, None, '/', None),
                (2, 1, 'what', None),
                (3, 2, 'you', None),
                (4, 3, 'at', None),
                (5, 4, 'gamma.vob', 'a=b\n'),
            ],
        )
        self.assertEqual(
            db.execute('SELECT * FROM tags').fetchall(),
            [
                ('a=b', 5),
            ],
        )

        polytaxis_monitor.main.remove_tags(fid)
        self.assertEqual(
            db.execute('SELECT * FROM tags').fetchall(),
            [],
        )

        polytaxis_monitor.main.delete_file(fid)
        self.assertEqual(
            db.execute('SELECT * FROM files').fetchall(),
            [],
        )

class TestQueryDB(unittest.TestCase):
    def setUp(self):
        db.execute('DELETE FROM tags')
        db.execute('DELETE FROM files')
        self.tag_sets = [
            {
                'seven': set([None]),
                'red': set([None]),
                'juicy': set([None]),
                'date': set(['99']),
            },
            {
                'seven': set([None]),
                'red': set([None]),
                'date': set(['98']),
            },
            {
                'seven': set([None]),
                'under': set([None]),
                'length': set(['7']),
                'date': set(['103']),
            },
        ]
        self.files = [
            ('/what/you/at/gamma.vob', self.tag_sets[0]),
            ('/home/hebwy/loog.txt', self.tag_sets[1]),
            ('/home/hebwy/noxx', self.tag_sets[2]),
        ]
        self.fids = []
        for filename, tags in self.files:
            fid = polytaxis_monitor.main.create_file(filename, tags)
            self.fids.append(fid)
            polytaxis_monitor.main.add_tags(fid, tags)
        with patch('polytaxis_monitor.common.open_db', new=lambda: (db, db_cursor)):
            self.query = polytaxis_monitor.common.QueryDB()

    def test_query_none(self):
        self.assertCountEqual(
            list(self.query.query([], [])),
            [
                {'fid': self.fids[0], 'segment': 'gamma.vob', 'tags': self.tag_sets[0]},
                {'fid': self.fids[1], 'segment': 'loog.txt', 'tags': self.tag_sets[1]},
                {'fid': self.fids[2], 'segment': 'noxx', 'tags': self.tag_sets[2]},
            ],
        )

    def test_query_include(self):
        self.assertCountEqual(
            list(self.query.query(['red'], [])),
            [
                {'fid': self.fids[0], 'segment': 'gamma.vob', 'tags': self.tag_sets[0]},
                {'fid': self.fids[1], 'segment': 'loog.txt', 'tags': self.tag_sets[1]},
            ],
        )
    
    def test_query_exclude(self):
        self.assertCountEqual(
            list(self.query.query([], ['juicy'])),
            [
                {'fid': self.fids[1], 'segment': 'loog.txt', 'tags': self.tag_sets[1]},
                {'fid': self.fids[2], 'segment': 'noxx', 'tags': self.tag_sets[2]},
            ],
        )
    
    def test_query_include_exclude(self):
        self.assertCountEqual(
            list(self.query.query(['seven', 'red'], ['date=99'])),
            [
                {'fid': self.fids[1], 'segment': 'loog.txt', 'tags': self.tag_sets[1]},
            ],
        )

    def test_query_path(self):
        self.assertEqual(
            self.query.query_path(self.fids[1]),
            '/home/hebwy/loog.txt',
        )

    def test_query_tags_prefix(self):
        self.assertEqual(
            list(self.query.query_tags('prefix', 'date=')),
            [
                'date=103',
                'date=98', 
                'date=99', 
            ],
        )

    def test_query_tags_anywhere(self):
        self.assertEqual(
            list(self.query.query_tags('anywhere', 'r')),
            [
                'red', 
                'under', 
            ],
        )

class TestCommon(unittest.TestCase):
    def test_parse_args(self):
        includes, excludes, filters, sort, columns = (
            polytaxis_monitor.common.parse_query([
                'key1',
                'key2=val2',
                'sort-:key3',
                'sort+:key3',
                'col:key4',
                '^key5',
                'key6<10',
                'key7<=11',
                'key8>12',
                'key9>=13',
                'key10=frog>prince',
            ])
        )
        self.assertCountEqual(
            includes, 
            [
                'key1',
                'key2=val2',
                'key6=%',
                'key7=%',
                'key8=%',
                'key9=%',
                'key10=frog>prince',
            ]
        )
        self.assertCountEqual(excludes, ['key5'])
        self.assertCountEqual(
            filters, 
            [
                (operator.lt, 'key6', '10'),
                (operator.le, 'key7', '11'),
                (operator.gt, 'key8', '12'),
                (operator.ge, 'key9', '13'),
            ]
        )
        self.assertEqual(sort, [('desc', 'key3'), ('asc', 'key3')])
        self.assertEqual(
            columns, 
            ['key3', 'key4', 'key6', 'key7', 'key8', 'key9'],
        )

    def test_sort(self):
        rows = [
            {'fid': 0, 'segment': '0', 'tags': {'1': {'a'}, '2': {'a'}}},
            {'fid': 1, 'segment': '1', 'tags': {'1': {'a'}, '2': {'b'}}},
            {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
        ]
        self.assertEqual(
            polytaxis_monitor.common.sort([('asc', '1'), ('desc', '2')], rows),
            [
                {'fid': 1, 'segment': '1', 'tags': {'1': {'a'}, '2': {'b'}}},
                {'fid': 0, 'segment': '0', 'tags': {'1': {'a'}, '2': {'a'}}},
                {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
            ],
        )
    
    def test_sort_missing(self):
        rows = [
            {'fid': 0, 'segment': '0', 'tags': {'2': {'a'}}},
            {'fid': 1, 'segment': '1', 'tags': {'2': {'b'}}},
            {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
        ]
        self.assertEqual(
            polytaxis_monitor.common.sort([('asc', '1'), ('desc', '2')], rows),
            [
                {'fid': 1, 'segment': '1', 'tags': {'2': {'b'}}},
                {'fid': 0, 'segment': '0', 'tags': {'2': {'a'}}},
                {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
            ],
        )

    def test_sort_nones(self):
        rows = [
            {'fid': 0, 'segment': '0', 'tags': {'1': None, '2': {'a'}}},
            {'fid': 1, 'segment': '1', 'tags': {'1': None, '2': {'b'}}},
            {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
        ]
        self.assertEqual(
            polytaxis_monitor.common.sort([('asc', '1'), ('desc', '2')], rows),
            [
                {'fid': 1, 'segment': '1', 'tags': {'1': None, '2': {'b'}}},
                {'fid': 0, 'segment': '0', 'tags': {'1': None, '2': {'a'}}},
                {'fid': 2, 'segment': '2', 'tags': {'1': {'b'}, '2': {'a'}}},
            ],
        )

    def test_filter(self):
        rows = [
            {'fid': 0, 'segment': '0', 'tags': {'a': {'1'}}},
            {'fid': 1, 'segment': '1', 'tags': {'a': {'2'}}},
            {'fid': 2, 'segment': '2', 'tags': {'a': {'3'}}},
        ]
        self.assertEqual(
            list(polytaxis_monitor.common.filter(
                [(operator.lt, 'a', '3')],
                rows, 
            )),
            [
                {'fid': 0, 'segment': '0', 'tags': {'a': {'1'}}},
                {'fid': 1, 'segment': '1', 'tags': {'a': {'2'}}},
            ],
        )
