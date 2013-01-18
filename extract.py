#!/usr/bin/env python

import requests # requires Python requests 1.x
import optparse
from openpyxl.workbook import Workbook
from openpyxl.writer.excel import ExcelWriter

debug = False

usage = """Convert data from a ScraperWiki box into an Excel spreadsheet.
Takes one argument: the full URL of the target box.
Example: ./extract.py http://box.scraperwiki.com/mybox/publish_token"""

def sqlite(dataset_box_url, q):
    if debug: print 'GET %s/sqlite?q=%s' % (dataset_box_url, q)
    return requests.get(dataset_box_url + '/sqlite', params={'q': q})

def extract():
    parser = optparse.OptionParser(usage=usage)
    (options, args) = parser.parse_args()

    if len(args):
        dataset_box_url = args[0]
        r = sqlite(dataset_box_url, 'select name from sqlite_master where type="table"')
        tables = [ x['name'] for x in r.json() ]

        wb = Workbook()
        wb.remove_sheet(wb.get_active_sheet())

        for table in tables:
            if debug: print table
            ws = wb.create_sheet(title=table)
            r2 = sqlite(dataset_box_url, 'select * from [%s]' % table)
            data = r2.json()
            ws.append(data[0].keys())
            for row in data:
                ws.append(row.values())

        wb.save(filename='http/spreadsheet.xlsx')
        if not debug:
            print '["spreadsheet.xlsx"]'

    else:
        print usage

try:
    extract()
except Exception as e:
    print '"We encountered a Python error while extracting your dataset: %s"' % e
    if debug: raise
