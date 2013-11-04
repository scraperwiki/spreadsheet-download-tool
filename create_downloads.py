#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import json
import os
import re
import traceback

from itertools import chain, izip, product
from datetime import datetime
from tempfile import NamedTemporaryFile
from os.path import abspath, dirname, join

import lxml.html
import requests
import unicodecsv
import xlwt

import scraperwiki

# how many rows to request from the SQL API at any one time
PAGE_SIZE = 5000

# where to put the resulting output files
DESTINATION = "./http"


class GeneratorReader(object):

    """
    Turn a generator-of-strings into a file-like object with a ``read``
    method.
    """

    def __init__(self, generator):
        self.generator = generator
        self._buf = []
        self._bufsize = 0
        self._total = 0

    def read(self, amount=None):
        if amount is None:
            return "".join(chain(self._buf, self.generator))

        # Retrieve enough from the generator to satisfy ``amount``
        while self._bufsize < amount:
            datum = next(self.generator, None)
            if datum is None:
                break
            self._buf.append(datum)
            self._bufsize += len(datum)

        data = self._buf

        # The last element of data must be too long.
        # Split it into two and push one part of it onto buf.
        if self._bufsize > amount:
            over = self._bufsize - amount
            left, right = data[-1][:-over], data[-1][-over:]
            data, self._buf = data[:-1] + [left], [right]
            self._bufsize = len(right)
        else:
            self._buf = []
            self._bufsize = 0

        result = b"".join(data)
        self._total += len(result)
        return result


def get_cell_span_content(cell):
    """
    Return the content and spanning of ``cell``, which may be a string or a
    lxml HTML <td>
    """
    if isinstance(cell, lxml.html.HtmlElement):
        colspan = int(cell.attrib.get("colspan", 1))
        rowspan = int(cell.attrib.get("rowspan", 1))
        content = cell.text_content()
    else:
        rowspan, colspan = 1, 1
        content = cell
    return (rowspan, colspan), content


def make_plain_table(table):
    """
    Given a table just containing strings, return it.

    If the table contains HTML td colspan elements, fill all spanned cells with
    its content to make the resulting table rectangular.

    TODO(pwaller): Make generator version of this.
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
        self.tempfile = NamedTemporaryFile(dir=dirname(path), delete=False)
        self.writer = unicodecsv.writer(self.tempfile, encoding='utf-8')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.tempfile.close()

        if exc_type is not None:
            os.unlink(self.tempfile.name)
            return

        os.rename(self.tempfile.name, self.path)
        os.chmod(self.path, 0644)

    def write_row(self, row):
        # TODO(pwaller): Deal with row/cell spans.
        self.writer.writerow(row)

    def write_rows(self, rows):
        self.writer.writerows(rows)


class ExcelOutput(object):

    def __init__(self, path):
        self.workbook = xlwt.Workbook(encoding="utf-8")
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        basepath = dirname(self.path)
        with NamedTemporaryFile(dir=basepath, delete=False) as tempfile:
            try:
                self.workbook.save(tempfile.name)
            except:
                os.unlink(tempfile.name)
                raise
            else:
                os.rename(tempfile.name, self.path)
                os.chmod(self.path, 0644)

    def add_sheet(self, sheet_name, table):
        sheet = self.workbook.add_sheet(sheet_name)

        for j, row in enumerate(table):
            for i, cell in enumerate(row):
                (rowspan, colspan), content = get_cell_span_content(cell)

                if colspan == rowspan == 1:
                    sheet.write(j, i, content)
                else:
                    sheet.write_merge(j, j + rowspan - 1,
                                      i, i + colspan - 1,
                                      content)


def main():
    log('# {} creating downloads:'.format(datetime.now().isoformat()))
    box_url = get_box_url()
    generate_for_box(box_url)


def paged_rows_generator(box_url, tables):
    for table in tables:
        yield get_paged_rows(box_url, table['name'])


def generate_for_box(box_url):

    save_state('all_tables.xls', None, None, 'generating')

    with ExcelOutput(join(DESTINATION, "all_tables.xls")) as excel_output:
        tables = get_dataset_tables(box_url)
        paged_rows = list(paged_rows_generator(box_url, tables))
        dump_tables(excel_output, tables, paged_rows)

        grids = get_dataset_grids(box_url)
        dump_grids(excel_output, grids)

    save_state('all_tables.xls', None, None, 'generated')


def make_table(columns, row_dicts):
    """
    Build a rectangular list-of-lists out of the table described by ``columns``
    and ``row_dicts``
    """

    yield columns

    for row in row_dicts:
        yield [row.get(column) for column in columns]


def write_excel_csv(excel_output, sheet_name, filename, rows):
    write_excel_row = excel_output.add_sheet(sheet_name)

    with CsvOutput(filename) as csv_output:
        write_csv_row = csv_output.write_row

        for row in rows:
            # Loop structure is intentionally this way because `grid_rows``
            # is a generator, and this is desirable for low memory usage.
            write_csv_row(row)
            write_excel_row(row)


def dump_tables(excel_output, tables, paged_rows):

    for table, paged_rows in izip(tables, paged_rows):
        rows = make_table(table['columns'], chain.from_iterable(paged_rows))

        filename = '{}.csv'.format(make_filename(table['name']))
        filename = join(DESTINATION, filename)

        save_state(filename, 'table', table['name'], 'generating')
        write_excel_csv(excel_output, table['name'], filename, rows)
        save_state(filename, 'table', table['name'], 'generated')


def dump_grids(excel_output, grids):

    for grid in grids:
        grid_rows = get_grid_rows(grid['url'])

        filename = '{}.csv'.format(make_filename(grid['name']))
        filename = join(DESTINATION, filename)

        save_state(filename, 'grid', grid['name'], 'generating')
        write_excel_csv(excel_output, grid['name'], filename, grid_rows)
        save_state(filename, 'grid', grid['name'], 'generated')


def get_dataset_tables(box_url):
    tables = []
    database_meta = get_database_meta(box_url)

    for table_name, table_meta in database_meta['table'].items():
        if not table_name.startswith('_'):
            tables.append({
                'id': table_name,
                'name': table_name,
                'columns': table_meta['columnNames'],
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
                'url': result['url'],
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


def grid_rows_from_string(text):
    """
    Note: this code is an improvement on ``grid_rows_from_string_old`` but
          still has very high memory requirements. Better to use
          ``generate_grid_rows``.
    """
    dom = lxml.html.fromstring(text)

    table = []
    row = []
    table.append(row)

    for element in dom.iter():
        if element.tag == "tr":
            row = []
            table.append(row)
        elif element.tag == "td":
            row.append(element)

    return table


def grid_rows_from_string_old(text):
    """
    Note: this code as O(N^2) performance on the number of rows and should be
        deleted. It is just here for comparison.
    """
    dom = lxml.html.fromstring(text)

    table = dom.cssselect('table')[0]

    trs = table.cssselect('tr')

    data = []
    for tr in trs:
        row = []
        data.append(row)

        for td in tr.cssselect('td'):
            row.append(td)

    return data


def get_grid_rows(grid_url):
    response = requests.get(grid_url)
    log("GET %s" % response.url)
    return grid_rows_from_string(response.text)


def find_trs(input_html):
    """
    Parse ``input_html`` streamwise, yielding one list per <tr> containing
    ``lxml.html.HtmlElement``.

    The row *must* be consumed immediately since the lxml.HtmlElement are
    destroyed to conserve memory.
    """
    parser = lxml.etree.iterparse(input_html, events=("end",))
    row = []

    for _, element in parser:

        if element.tag == "td":
            row.append(element)
            continue

        if element.tag == "tr":
            yield row

            row[:] = []

        # These few lines make the memory requirements go from as high as
        # 8 GB to ~1MB when parsing large files.
        element.clear()
        while element.getprevious() is not None:
            del element.getparent()[0]


def generate_grid_rows(grid_url):
    """
    Lazy generator of rows for the grid at ``grid_url``.

    Doesn't cause the whole grid to be loaded into memory at any one time, so
    has very low memory requirements.

    Rows *must* be consumed immediately.
    """
    response = requests.get(url, stream=True)
    # Note: this happens to be the size that lxml.etree.iterparse uses when
    #       parsing file-like objects. It doesn't have a very big impact on
    #       performance.
    CHUNK_SIZE = 32 * 1024
    return find_trs(GeneratorReader(response.iter_content(CHUNK_SIZE)))


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
        'source_id': source_id,
    }, '_state_files')


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
