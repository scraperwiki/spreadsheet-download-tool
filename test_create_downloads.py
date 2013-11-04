import mock

from io import BytesIO
from resource import getrusage, RUSAGE_SELF, getpagesize
from textwrap import dedent

from nose.tools import assert_equal, assert_less_equal

from create_downloads import (ExcelOutput, CsvOutput, grid_rows_from_string,
                              make_plain_table, dump_grids, find_trs)


def test_generate_excel():
    with open("test/fixtures/simple-table-colspans.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with ExcelOutput("test/test.xls") as excel_output:
        excel_output.add_sheet("test_sheet", grid_rows)

    csv_rows = make_plain_table(grid_rows)
    with CsvOutput("test/test.csv") as csv_output:
        csv_output.write_rows(csv_rows)


def getmaxrss_mb():
    ru = getrusage(RUSAGE_SELF)

    def as_mb(n_pages):
        return n_pages * getpagesize() / 1024. ** 2

    before, after = None, None

    # import gc
    # before = gc.get_count(), len(gc.get_objects())
    # gc.collect()
    # after = gc.get_count(), len(gc.get_objects())

    return as_mb(ru.ru_maxrss)  # , before, after


def make_table(nrows, ncols):

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
    while delta < 1:
        delta = getmaxrss_mb() - mem_before
        # Take another 1MB of memory..
        keep_alive.append(" " * (1024 * 1024))
        print "Allocated 1MB.."
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


