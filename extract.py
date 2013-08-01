#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests  # requires Python requests 1.x
import xlwt
import unicodecsv
import json
import collections
import scraperwiki
from tempfile import mkstemp
import os
import sys
from os.path import join, abspath, dirname
import traceback

DEBUG = True  # prints debug messages to stdout during run

MAX_ROWS = 5000  # how many rows to request from the SQL API at any one time

USAGE = """Convert data from a ScraperWiki box into CSVs and Excel
spreadsheets.  Reads from a file in the home directory containing  the full URL
of the target box, including publishToken, ie
http://box.scraperwiki.com/boxName/publishToken
"""


class CsvOutput(object):
    def __init__(self):
        self.tempfiles = {}
        self.writers = {}

    def add_table(self, table_name, column_names):
        self.tempfiles[table_name] = make_temp_file('.csv')
        f = open(self.tempfiles[table_name], 'w')
        self.writers[table_name] = unicodecsv.DictWriter(f, column_names)
        self.writers[table_name].writeheader()

        save_state("%s.csv" % table_name, 'creating')

    def write_rows(self, table_name, rows):
        self.writers[table_name].writerows(rows)

    def finalise(self):
        for table_name, tempfile in self.tempfiles.items():
            replace_tempfile(tempfile, "http/{}.csv".format(table_name))
            save_state("{}.csv".format(table_name), 'completed')
        self.tempfiles = {}
        self.writers = {}


class ExcelOutput(object):
    def __init__(self):
        self.workbook = xlwt.Workbook(encoding="utf-8")
        self.name = 'all_tables.xls'
        self.sheets = {}
        self.current_rows = {}
        save_state(self.name, 'creating')

    def add_table(self, table_name, column_names):
        self.sheets[table_name] = self.workbook.add_sheet(table_name)
        for col_number, value in enumerate(column_names):
            self.sheets[table_name].write(0, col_number, value)
        self.current_rows[table_name] = 1

    def write_rows(self, table_name, rows):
        for row in rows:
            self.write_row(table_name, row)

    def write_row(self, table_name, row):
        for col_number, cell_value in enumerate(row.values()):
            self.sheets[table_name].write(
                self.current_rows[table_name],
                col_number,
                cell_value)
            self.current_rows[table_name] += 1

    def finalise(self):
        tempfile = make_temp_file('.xls')
        self.workbook.save(tempfile)
        replace_tempfile(tempfile, 'http/{}'.format(self.name))
        save_state(self.name, 'completed')


def main():
    (box_url, tables_and_columns) = setup()

    csv_output = CsvOutput()
    excel_output = ExcelOutput()

    for table_name, column_names in tables_and_columns.items():
        csv_output.add_table(table_name, column_names)
        excel_output.add_table(table_name, column_names)

        for chunk_of_rows in get_rows(box_url, table_name):
            csv_output.write_rows(table_name, chunk_of_rows)
            excel_output.write_rows(table_name, chunk_of_rows)

    csv_output.finalise()
    excel_output.finalise()


def setup():
    box_url = get_box_url()
    create_state_table()

    tables_and_columns = get_tables_and_columns(box_url)
    log(tables_and_columns)
    return box_url, tables_and_columns


def create_state_table():
    scraperwiki.sql.execute(
        'CREATE TABLE IF NOT EXISTS "_state" ("filename" UNIQUE, "created")')
    scraperwiki.sql.commit()


def get_box_url():
    try:
        filename = abspath(join(dirname(__file__), '..', 'dataset_url.txt'))
        with open(filename, 'r') as f:
            return f.read().strip()
    except IOError:
        print("ERROR: No dataset URL in {}, try hitting regenerate.\n".format(
              filename))
        print(USAGE)
        sys.exit(1)


def make_temp_file(suffix):
    (_, filename) = mkstemp(suffix=suffix, dir='http')
    os.chmod(filename, 0644)  # world-readable
    return filename


def replace_tempfile(tmp, destination):
    os.rename(tmp, destination)


def log(string):
    if DEBUG:
        print string


def call_api(box_url, params=None):
    # returns sql api output as a Python dict/list
    log("call_api(%s)" % box_url)
    response = requests.get(box_url, params=params)
    log("GET %s" % response.url)
    if response.status_code == requests.codes.ok:
        return json.loads(response.content,
                          object_pairs_hook=collections.OrderedDict)
    else:
        response.raise_for_status()


def query_sql_database(box_url, query):
    return call_api("%s/sql" % box_url, {"q": query})


def get_database_meta(box_url):
    return call_api("%s/sql/meta" % box_url)


def get_tables_and_columns(box_url):
    # returns a dict of lists, like so:
    # { tableOne: [ col1, col2 ], tableTwo: […, …] }
    meta = get_database_meta(box_url)
    result = {}
    for table_name in meta['table'].keys():
        result[table_name] = meta['table'][table_name]['columnNames']
    return result


def get_rows(box_url, table_name):
    start = 0
    while True:
        rows = query_sql_database(
            box_url, 'SELECT * FROM "%s" LIMIT %d, %d' % (
                table_name, start, MAX_ROWS))
        if not rows:
            break
        yield rows
        start += MAX_ROWS


def save_state(filename, state):
    log("%s %s" % (filename, state))
    if state == 'creating':
        scraperwiki.sql.save(
            unique_keys=['filename'],
            data={
                'filename': filename,
                "created": None},
            table_name='_state')
    elif state == 'completed':
        now = scraperwiki.sql.select('datetime("now") as now')[0]['now']
        scraperwiki.sql.save(
            ['filename'], {'filename': filename, "created": now}, '_state')
    else:
        raise Exception("Unknown status: %s" % state)

try:
    scraperwiki.sql.execute("drop table if exists _error")
    scraperwiki.sql.commit()
    main()
except Exception as e:
    print('Error while extracting your dataset: %s' % e)
    scraperwiki.sql.save(
        unique_keys=['message'],
        data={'message': traceback.format_exc()},
        table_name='_error')
    raise
