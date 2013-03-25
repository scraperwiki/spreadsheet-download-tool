#!/usr/bin/env python

import requests # requires Python requests 1.x
import optparse
from openpyxl.workbook import Workbook
from openpyxl.writer.excel import ExcelWriter
import unicodecsv
import json

debug = False

usage = """Convert data from a ScraperWiki box into a CSV or Excel spreadsheet.
Takes two arguments: format (csv or xlsx) and the full URL of the target box.
Example: ./extract.py xlsx http://box.scraperwiki.com/mybox/publish_token"""

def sqlite(dataset_box_url, q):
    if debug: print 'GET %s/sqlite?q=%s' % (dataset_box_url, q)
    return requests.get(dataset_box_url + '/sql', params={'q': q})

def sqlite_meta(dataset_box_url):
    if debug: print 'GET %s/sqlite/meta' % (dataset_box_url)
    return requests.get(dataset_box_url + '/sql/meta')

def extract(dataset_box_url):
    sheets = {}
    meta = sqlite_meta(dataset_box_url).json()
    table_names = [ x for x in meta['table'] ]
    for table_name in table_names:
        r2 = sqlite(dataset_box_url, 'select * from [%s]' % table_name)
        sheets[table_name] = r2.json()
    return sheets

def save(type, sheets):
    if debug: print 'saving', type, len(sheets), 'sheet(s)'
    if type == 'xlsx':
        wb = Workbook(optimized_write = True)
        # wb.remove_sheet(wb.get_active_sheet())
        for sheet_name, sheet in sheets.items():
            if debug: sheet_name
            ws = wb.create_sheet(title=sheet_name)
            ws.append(sheet[0].keys())
            for row in sheet:
                ws.append(row.values())
        wb.save(filename='http/spreadsheet.xlsx')
        if not debug:
            print '["http/spreadsheet.xlsx"]'
    elif type == 'csv':
        files = []
        for sheet_name, sheet in sheets.items():
            with open('http/%s.csv' % sheet_name, 'wb') as f:
                writer = unicodecsv.DictWriter(f, sheet[0].keys())
                writer.writeheader()
                writer.writerows(sheet)
                files.append('http/%s.csv' % sheet_name)
        if not debug:
            print json.dumps(files)

def main():
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-t", "--type", type="choice", choices=['csv', 'xlsx'], help="Desired file format (csv or xlsx)")
    (options, args) = parser.parse_args()

    if len(args) == 1:
        sheets = extract(args[0])
        save(options.type, sheets)
    else:
        print parser.get_usage()

try:
    main()
except Exception as e:
    print '"We encountered a Python error while extracting your dataset: %s"' % e
    if debug: raise
