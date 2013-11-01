#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import json
import os
import re
import traceback

from itertools import product
from datetime import datetime
from tempfile import mkstemp
from os.path import join, abspath, dirname

import lxml.html
import requests
import unicodecsv
import xlwt

import scraperwiki

# how many rows to request from the SQL API at any one time
PAGE_SIZE = 5000


def get_cell_span_content(cell):
    """
    Return the content and spanning of ``cell``, which may be a string or a
    lxml HTML <td>
    """
    if isinstance(cell, basestring):
        rowspan, colspan = 1, 1
        content = cell
    else:
        assert isinstance(cell, lxml.html.HtmlElement)
        colspan = int(cell.attrib.get("colspan", 1))
        rowspan = int(cell.attrib.get("rowspan", 1))
        content = cell.text_content()
    return (rowspan, colspan), content


def make_plain_table(table):
    """
    Given a table just containing strings, return it.

    If the table contains HTML td colspan elements, fill all spanned cells with
    its content.
    """
    if all(isinstance(cell, basestring) for row in table for cell in row):
        # No transformation needed
        return table

    # If we get here, table contains lxml.html.HtmlElement which may be
    # colspanned. Undo the colspanning.

    result_table = []

    def insert(j, i, content):
        n_missing_rows = j - len(result_table) + 1
        if n_missing_rows > 0:
            result_table.extend(list() for _ in xrange(n_missing_rows))

        row = result_table[j]
        n_missing_cells = i - len(row) + 1
        if n_missing_cells > 0:
            row.extend("" for _ in xrange(n_missing_cells))

        row[i] = content

    for j, row in enumerate(table):
        for i, cell in enumerate(row):
            (rowspan, colspan), content = get_cell_span_content(cell)

            if colspan == rowspan == 1:
                insert(j, i, content)
                continue

            for y, x in product(xrange(rowspan), xrange(colspan)):
                insert(j + y, i + x, content)

    return result_table


class CsvOutput(object):

    def __init__(self):
        self.tempfiles = {}
        self.writers = {}

    def add_table(self, table_name, column_names):
        self.tempfiles[table_name] = make_temp_file('.csv')
        f = open(self.tempfiles[table_name], 'w')
        self.writers[table_name] = unicodecsv.DictWriter(f, column_names)
        self.writers[table_name].writeheader()

    def add_grid(self, grid_name):
        self.tempfiles[grid_name] = make_temp_file('.csv')
        f = open(self.tempfiles[grid_name], 'w')
        self.writers[grid_name] = unicodecsv.writer(f, encoding='utf-8')

    def write_rows(self, table_name, rows):
        plain_rows = make_plain_table(rows)
        self.writers[table_name].writerows(plain_rows)

    def finalise_file(self, table_name):
        replace_tempfile(self.tempfiles[table_name],
                         "http/{}.csv".format(make_filename(table_name)))
        del self.tempfiles[table_name]
        del self.writers[table_name]

    # not used any more
    def finalise_all(self):
        for table_name, tempfile in self.tempfiles.items():
            replace_tempfile(
                tempfile, "http/{}.csv".format(make_filename(table_name)))
        self.tempfiles = {}
        self.writers = {}


class ExcelOutput(object):

    def __init__(self):
        self.workbook = xlwt.Workbook(encoding="utf-8")
        self.name = 'all_tables.xls'
        self.sheets = {}
        self.current_rows = {}
        self.fail = False

    def add_table(self, table_name, column_names):
        self.sheets[table_name] = self.workbook.add_sheet(table_name)
        for col_number, value in enumerate(column_names):
            self.sheets[table_name].write(0, col_number, value)
        self.current_rows[table_name] = 1

    def add_grid(self, grid_name):
        self.sheets[grid_name] = self.workbook.add_sheet(grid_name)
        self.current_rows[grid_name] = 0

    def write_rows(self, table_name, rows):

        write_cell = self.sheets[table_name].write
        write_cell_merged = self.sheets[table_name].write_merge

        for j, row in enumerate(rows):
            for i, cell in enumerate(row):
                (rowspan, colspan), content = get_cell_span_content(cell)

                if colspan == rowspan == 1:
                    write_cell(j, i, content)
                else:
                    write_cell_merged(j, j+rowspan-1, i, i+colspan-1, content)

    def finalise(self):
        output_name = 'http/{}'.format(self.name)
        if self.fail:
            save_state(self.name, None, None, 'failed')
            os.path.exists(output_name) and os.remove(output_name)
            return
        tempfile = make_temp_file('.xls')
        self.workbook.save(tempfile)
        replace_tempfile(tempfile, output_name)


def main():
    log('# {} creating downloads:'.format(datetime.now().isoformat()))
    box_url = get_box_url()
    generate_for_box(box_url)


def generate_for_box(box_url):
    tables = get_dataset_tables(box_url)
    grids = get_dataset_grids(box_url)
    dump_tables_grids(box_url, tables, grids)


def dump_tables_grids(box_url, tables, grids):
    csv_outputter = CsvOutput()
    xls_outputter = ExcelOutput()

    save_state('all_tables.xls', None, None, 'generating')

    for table in tables:
        save_state('{}.csv'.format(
                   make_filename(table['name'])),
                   'table', table['name'], 'generating')

        csv_outputter.add_table(table['name'], table['columns'])
        xls_outputter.add_table(table['name'], table['columns'])

        for some_rows in get_paged_rows(box_url, table['name']):
            csv_outputter.write_rows(table['name'], some_rows)
            xls_outputter.write_rows(table['name'], some_rows)

        csv_outputter.finalise_file(table['name'])

        save_state("{}.csv".format(make_filename(table['name'])),
                   'table', table['name'], 'generated')

    for grid in grids:
        save_state('{}.csv'.format(make_filename(grid['name'])),
                   'grid', grid['name'], 'generating')

        csv_outputter.add_grid(grid['name'])
        xls_outputter.add_grid(grid['name'])

        grid_rows = get_grid_rows(grid['url'])

        csv_outputter.write_rows(grid['name'], grid_rows)
        xls_outputter.write_rows(grid['name'], grid_rows)

        csv_outputter.finalise_file(grid['name'])

        save_state("{}.csv".format(make_filename(grid['name'])),
                   'grid', grid['name'], 'generated')

    xls_outputter.finalise()

    save_state('all_tables.xls', None, None, 'generated')


def get_dataset_tables(box_url):
    tables = []
    database_meta = get_database_meta(box_url)
    for table_name, table_meta in database_meta['table'].items():
        if not table_name.startswith('_'):
            tables.append({
                'id': table_name,
                'name': table_name,
                'columns': table_meta['columnNames']
            })
    return tables


def get_dataset_grids(box_url):
    grids = []
    try:
        results = query_sql_database(box_url, 'SELECT * FROM _grids')
        for result in results:
            grids.append({
                'id': result['checksum'],
                'name': result['title'],
                'url': result['url']
            })
    except Exception as e:
        log('could not get _grids:')
        log(e)

    return grids


def log(string):
    print string


def get_box_url():
    filename = abspath(join(dirname(__file__), '..', 'dataset_url.txt'))
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except IOError:
        raise RuntimeError("ERROR: No dataset URL in {}".format(filename))


def call_api(box_url, params=None):
    # returns sql api output as a Python dict/list
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


def get_paged_rows(box_url, table_name):
    start = 0
    while True:
        q = 'SELECT * FROM "%s" LIMIT %d, %d' % (table_name, start, PAGE_SIZE)
        rows = query_sql_database(box_url, q)
        if not rows:
            break
        yield rows
        start += PAGE_SIZE


def get_grid_rows(grid_url):
    response = requests.get(grid_url)
    log("GET %s" % response.url)
    dom = lxml.html.fromstring(response.text)
    table = dom.cssselect('table')[0]

    data = []
    for tr in table.cssselect('tr'):
        row = []
        data.append(row)

        for td in tr.cssselect('td'):
            row.append(td)

    return data


def save_state(filename, source_type, source_id, state):
    log("%s %s" % (filename, state))
    if state in ['generating', 'waiting', 'failed']:
        scraperwiki.sql.save(['filename'], {
            'filename': filename,
            'state': state,
            'created': None,
            'source_type': source_type,
            'source_id': source_id
        }, '_state_files')
    elif state == 'generated':
        scraperwiki.sql.save(['filename'], {
            'filename': filename,
            'state': 'generated',
            'created': '{}+00:00'.format(datetime.now().isoformat()),
            'source_type': source_type,
            'source_id': source_id
        }, '_state_files')
    else:
        raise Exception("Unknown status: %s" % state)


def make_temp_file(suffix):
    (_, filename) = mkstemp(suffix=suffix, dir='http')
    os.chmod(filename, 0644)  # world-readable
    return filename


def replace_tempfile(tmp, destination):
    os.rename(tmp, destination)


def make_filename(naughty_string):
    # if you change this function, make sure to
    # also change the one in code.js
    s = naughty_string.lower()
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^a-z0-9-_.]+', '', s)
    return s


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print('Error while extracting your dataset: %s' % e)
        scraperwiki.sql.save(
            unique_keys=['message'],
            data={'message': traceback.format_exc()},
            table_name='_error')
        raise
