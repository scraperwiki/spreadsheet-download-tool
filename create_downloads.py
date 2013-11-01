#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import json
import os
import re
import traceback

from itertools import product
from datetime import datetime
from tempfile import NamedTemporaryFile
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
    its content to make the resulting table rectangular.
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

    def __init__(self, path):
        self.path = path
        self.tempfile = NamedTemporaryFile(dir=".", delete=False)
        self.writer = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.tempfile.close()

        if exc_type is not None:
            os.unlink(self.tempfile.name)
            return

        os.rename(self.tempfile.name, self.path)

    def add_table(self, table_name, column_names):
        self.writer = unicodecsv.DictWriter(self.tempfile, column_names)
        self.writer.writeheader()

    def add_grid(self, grid_name):
        self.writer = unicodecsv.writer(self.tempfile, encoding='utf-8')

    def write_rows(self, table_name, rows):
        plain_rows = make_plain_table(rows)
        self.writer.writerows(plain_rows)


class ExcelOutput(object):

    def __init__(self, path):
        self.workbook = xlwt.Workbook(encoding="utf-8")
        self.path = path
        self.sheets = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        with NamedTemporaryFile(dir=".", delete=False) as tempfile:
            try:
                self.workbook.save(tempfile.name)
            except:
                os.unlink(tempfile.name)
                raise
            else:
                os.rename(tempfile.name, self.path)

    def add_table(self, table_name, column_names):
        self.sheets[table_name] = self.workbook.add_sheet(table_name)
        for col_number, value in enumerate(column_names):
            self.sheets[table_name].write(0, col_number, value)

    def add_grid(self, grid_name):
        self.sheets[grid_name] = self.workbook.add_sheet(grid_name)

    def write_rows(self, table_name, rows):

        write_cell = self.sheets[table_name].write
        write_cell_merged = self.sheets[table_name].write_merge

        for j, row in enumerate(rows):
            for i, cell in enumerate(row):
                (rowspan, colspan), content = get_cell_span_content(cell)

                if colspan == rowspan == 1:
                    write_cell(j, i, content)
                else:
                    write_cell_merged(j, j + rowspan - 1,
                                      i, i + colspan - 1,
                                      content)


def main():
    log('# {} creating downloads:'.format(datetime.now().isoformat()))
    box_url = get_box_url()
    generate_for_box(box_url)


def generate_for_box(box_url):

    save_state('all_tables.xls', None, None, 'generating')

    with ExcelOutput("http/all_tables.xls") as excel_output:
        tables = get_dataset_tables(box_url)
        dump_tables(box_url, excel_output, tables)

        grids = get_dataset_grids(box_url)
        dump_grids(excel_output, grids)

    save_state('all_tables.xls', None, None, 'generated')


def dump_tables(box_url, excel_output, tables):

    for table in tables:
        filename = '{}.csv'.format(make_filename(table['name']))
        save_state(filename, 'table', table['name'], 'generating')

        with CsvOutput(filename) as csv_output:

            for some_rows in get_paged_rows(box_url, table['name']):

                csv_output.add_table(table['name'], table['columns'])
                csv_output.write_rows(table['name'], some_rows)

                excel_output.add_table(table['name'], table['columns'])
                excel_output.write_rows(table['name'], some_rows)

        save_state(filename, 'table', table['name'], 'generated')


def dump_grids(excel_output, grids):

    for grid in grids:
        filename = '{}.csv'.format(make_filename(grid['name']))
        save_state(filename, 'grid', grid['name'], 'generating')

        with CsvOutput(filename) as csv_output:
            rows = get_grid_rows(grid['url'])

            csv_output.add_grid(grid['name'])
            csv_output.write_rows(grid['name'], rows)

            excel_output.add_grid(grid['name'])
            excel_output.write_rows(grid['name'], rows)

        save_state(filename, 'grid', grid['name'], 'generated')


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

    created = None
    if state == 'generated':
        created = '{}+00:00'.format(datetime.now().isoformat())

    if state not in ['generating', 'waiting', 'failed', 'generated']:
        raise Exception("Unknown status: {0}".format(state))

    scraperwiki.sql.save(['filename'], {
        'filename': filename,
        'state': state,
        'created': created,
        'source_type': source_type,
        'source_id': source_id
    }, '_state_files')


def make_temp_file(suffix):
    (_, filename) = mkstemp(suffix=suffix, dir='http')
    os.chmod(filename, 0644)  # world-readable
    return filename


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
