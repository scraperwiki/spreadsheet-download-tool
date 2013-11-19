import mock

from io import BytesIO
from resource import getrusage, RUSAGE_SELF, getpagesize
from textwrap import dedent

from nose.tools import assert_equal, assert_less_equal
from nose.plugins.skip import SkipTest

from create_downloads import (ExcelOutput, CsvOutput, grid_rows_from_string,
                              make_plain_table, dump_grids, find_trs)


def test_generate_excel_colspans():
    # This test doesn't actually check the output, it just exercises the code.
    # :(

    with open("test/fixtures/simple-table-colspans.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with ExcelOutput("test/test.xls") as excel_output:
        add_row = excel_output.add_sheet("test_sheet")

        for row in grid_rows:
            add_row(row)

def test_generate_excel_colspans_complex():
    # This test doesn't actually check the output, it just exercises the code.
    # :(

    with open("test/fixtures/more-complicated-colspan.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with ExcelOutput("test/test.xls") as excel_output:
        add_row = excel_output.add_sheet("test_sheet")

        for row in grid_rows:
            add_row(row)


def test_generate_csv_rowspans():
    raise SkipTest("Unskip this when rowspanning is implemented correctly")

    with open("test/fixtures/simple-table-rowspans.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with mock.patch("create_downloads.CsvOutput._send_row") as _send_row:
        with CsvOutput("test/test-rowspans.csv") as csv_output:
            for row in grid_rows:
                csv_output.write_row(row)

        from mock import call
        expected = [
            call([u'Name: \u201cBlad1\u201d', u'Name: \u201cBlad1\u201d',
                  u'Name: \u201cBlad1\u201d', u'Name: \u201cBlad1\u201d']),
            call(['Table: 1', 'Table: 1', 'Table: 1', 'Table: 1']),
            call(['', '', '', '']),
            call(['Port', '31 December 2012', '31 January 2013',
                  'Difference']),
            call(['Port', '', '', '']),
            call(['Antwerp', '4827966.66667', '4947533.33333',
                  '119566.666667']),
            call(['Bremen', '1265600.0', '1344250.0', '78650.0']),
            call(['Hamburg', '1593400.0', '1653916.66667', '60516.6666667']),
            call(['Genova', '934993.0', '947459.0', '12466.0']),
            call(['Le Havre', '445833.333333', '479983.333333', '34150.0']),
            call(['Trieste', '695243.0', '702157.0', '6914.0']),
            call(['Total Europe', '9763036.0', '10075299.3333',
                  '312263.333333'])]

        # The intent of this test is to ensure that colspans are correctly
        # copied to all of the destination cells which are overlapped by it.
        assert_equal(expected, _send_row.call_args_list)


def test_generate_csv_colspans():
    with open("test/fixtures/simple-table-colspans.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with mock.patch("create_downloads.CsvOutput._send_row") as _send_row:
        with CsvOutput("test/test.csv") as csv_output:
            for row in grid_rows:
                csv_output.write_row(row)

        from mock import call
        expected = [
            call([u'Name: \u201cBlad1\u201d', u'Name: \u201cBlad1\u201d',
                  u'Name: \u201cBlad1\u201d', u'Name: \u201cBlad1\u201d']),
            call(['Table: 1', 'Table: 1', 'Table: 1', 'Table: 1']),
            call(['', '', '', '']),
            call(['Port', '31 December 2012', '31 January 2013',
                  'Difference']),
            call(['', '', '', '']),
            call(['Antwerp', '4827966.66667', '4947533.33333',
                  '119566.666667']),
            call(['Bremen', '1265600.0', '1344250.0', '78650.0']),
            call(['Hamburg', '1593400.0', '1653916.66667', '60516.6666667']),
            call(['Genova', '934993.0', '947459.0', '12466.0']),
            call(['Le Havre', '445833.333333', '479983.333333', '34150.0']),
            call(['Trieste', '695243.0', '702157.0', '6914.0']),
            call(['Total Europe', '9763036.0', '10075299.3333',
                  '312263.333333'])]

        # The intent of this test is to ensure that colspans are correctly
        # copied to all of the destination cells which are overlapped by it.
        assert_equal(expected, _send_row.call_args_list)


def test_dump_grids():
    with mock.patch("create_downloads.get_grid_rows") as get_grid_rows, \
            mock.patch("create_downloads.CsvOutput.write_row") as write_row:

        rows = [
            [1, 2, 3, 4],
            [1, 2, 3, 4],
            [1, 2, 3, 4],
        ]

        def get_rows(*args):
            return rows

        get_grid_rows.side_effect = get_rows

        # class MockExcel():

        #     def add_sheet(self, name):
        #         def write_row(row):
        #             pass
        #         return write_row

        with ExcelOutput("test/test_all_tables.xls") as excel_output:
            grids = [{'name': '<name>', 'url': '<url>'}]
            dump_grids(excel_output, grids)

        # assert_equal(   ) write_row.call_args_list


def getmaxrss_mb():
    """
    Return the maximum resident memory usage of this process
    """
    ru = getrusage(RUSAGE_SELF)

    def as_mb(n_pages):
        return n_pages * getpagesize() / 1024. ** 2

    return as_mb(ru.ru_maxrss)


def make_table(nrows, ncols):
    """
    Return a simple HTML table with nrows ncols.
    """

    return dedent(b"""\
        <table>
        {rows}
        </table>
        """).format(
        rows="\n".join(
            "<tr>{cells}</tr>".format(cells="".join("<td>{i}</td>".format(i=i)
                                      for i in xrange(ncols)))
            for _ in xrange(nrows)))


def kick_maxrss():
    """
    Return an object, which if kept alive, guarantees that the maximum resident
    memory of the process is roughly equal to the current usage.
    """
    delta = 0
    mem_before = getmaxrss_mb()
    keep_alive = []
    # Algorithm: whilst delta doesn't go up, more memory needs to be allocated.
    MiB = (1024 * 1024)
    while delta < 1:
        delta = getmaxrss_mb() - mem_before
        # Take another 1MB of memory..
        keep_alive.append(" " * MiB)

    print "Allocated {0}MiB..".format(len(keep_alive))
    return keep_alive


def test_mem_parse_giant_table():

    # Note: this test really wants to be run by itself in a process since it
    #       measures the *max* rss of the whole program. If python allocates
    #       a large object which goes away, the test will lie to us. Hence,
    #       kick_maxrss().
    alive = kick_maxrss()

    # Note: this has been tested with 1M row, and it works but it's slow.
    # 100krow makes the point.
    N_ROWS = 100000

    table = make_table(N_ROWS, 4)

    mem_before = getmaxrss_mb()

    n = 0
    for row in find_trs(BytesIO(table)):
        n += 1

    used = getmaxrss_mb() - mem_before

    assert_equal(N_ROWS, n)

    # Check that we didn't use more than 1MB to parse the table.
    assert_less_equal(used, 1)


def test_mem_generate_excel():

    alive = kick_maxrss()

    # Note: this has been tested with 1M row, and it works but it's slow.
    # 100krow makes the point.
    N_ROWS = 80000

    table = make_table(N_ROWS, 4)

    mem_before = getmaxrss_mb()
    # outputter = ExcelOutput
    outputter = ExceleratorOutput
    # outputter = XlsxWriterOutput

    with outputter("test/test_mem_generate_excel.xlsx") as xls:
        n = 0
        write_row = xls.add_sheet("hi")

        with t("write rows"):
            for row in find_trs(BytesIO(table)):
                write_row([e.text for e in row])

    used = getmaxrss_mb() - mem_before

    print "Used MB for 65krow:", used
