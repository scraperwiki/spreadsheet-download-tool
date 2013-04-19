#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests # requires Python requests 1.x
import optparse
from openpyxl.workbook import Workbook
from openpyxl.writer.excel import ExcelWriter
import unicodecsv
import json
import collections

DEBUG = False # prints debug messages to stdout during run

MAX_ROWS = 5000 # how many rows to request from the SQL API at any one time

USAGE = """Convert data from a ScraperWiki box into a CSV or Excel spreadsheet.
Takes two arguments: format (csv or xlsx) and the full URL of the target box.
Example: ./extract.py --type xlsx http://box.scraperwiki.com/boxName/publishToken"""

def main():
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option("-t", "--type", type="choice", choices=['csv', 'xlsx'], help="Desired file format (csv or xlsx)")
    (options, args) = parser.parse_args()
    try:
        box_url = args[0]
    except IndexError:
        parser.error("No box url specified")

    # a dict of lists, like so:
    # { tableOne: [ col1, col2 ], tableTwo: […, …] }
    tables_and_columns = get_tables_and_columns(box_url)
    log(tables_and_columns)

    if options.type == 'csv':
        filenames = []
        for table_name, column_names in tables_and_columns.items():
            filename = 'http/%s.csv' % table_name
            with open(filename, 'wb') as f:
                writer = unicodecsv.DictWriter(f, column_names)
                writer.writeheader()
                for chunk_of_rows in get_rows(box_url, table_name):
                    writer.writerows(chunk_of_rows)
            filenames.append(filename)
    else:
        wb = Workbook(optimized_write = True)
        for table_name, column_names in tables_and_columns.items():
            ws = wb.create_sheet(title=table_name)
            ws.append(column_names)
            for chunk_of_rows in get_rows(box_url, table_name):
                for row in chunk_of_rows:
                    ws.append(row.values())
        wb.save(filename='http/spreadsheet.xlsx')
        filenames = ['http/spreadsheet.xlsx']
    print json.dumps(filenames)

def log(string):
    if DEBUG: print string

def call_api(box_url, params=None):
    # returns sql api output as a Python dict/list
    log("call_api(%s)" % box_url)
    response = requests.get(box_url, params=params)
    log("GET %s" % response.url)
    if response.status_code == requests.codes.ok:
        return json.loads(response.content, object_pairs_hook=collections.OrderedDict)
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
        rows = query_sql_database(box_url, """SELECT * FROM "%s" LIMIT %d, %d""" % (table_name, start, MAX_ROWS))
        if not rows:
            break
        yield rows
        start += MAX_ROWS

try:
    main()
except Exception as e:
    print '"We encountered a Python error while extracting your dataset: %s"' % e
    if DEBUG: raise
