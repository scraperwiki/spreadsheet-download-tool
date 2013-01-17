#!/usr/bin/env python

import requests
from openpyxl.workbook import Workbook
from openpyxl.writer.excel import ExcelWriter

debug = False

def sqlite(dataset_box_url, q):
    if debug: print 'GET %s/sqlite?q=%s' % (dataset_box_url, q)
    return requests.get(dataset_box_url + '/sqlite', params={'q': q})

def extract(dataset_box_url):
    r = sqlite(dataset_box_url, 'select name from sqlite_master where type="table"')
    tables = [ x['name'] for x in r.json ]

    wb = Workbook()
    wb.remove_sheet(wb.get_active_sheet())

    for table in tables:
        if debug: print table
        ws = wb.create_sheet(title=table)
        r = sqlite(dataset_box_url, 'select * from [%s]' % table)
        data = r.json
        ws.append(data[0].keys())
        for row in data:
            ws.append(row.values())
        ws.cell(row=1, column=1).value = table

    wb.save(filename='http/spreadsheet.xlsx')
    if not debug:
        print '["spreadsheet.xlsx"]'


try:
    extract('https://box.scraperwiki.com/zarino.lastfm/f2cf672ac2b8405')
except Exception as e:
    print '"We encountered a Python error while extracting your dataset: %s"' % e
    if debug: raise
