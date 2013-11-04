from create_downloads import (ExcelOutput, CsvOutput, grid_rows_from_string,
                              make_plain_table)


def test_generate_excel():
    with open("test/fixtures/simple-table-colspans.html") as fd:
        grid_rows = grid_rows_from_string(fd.read())

    with ExcelOutput("test/test.xls") as excel_output:
        excel_output.add_sheet("test_sheet", grid_rows)

    csv_rows = make_plain_table(grid_rows)
    with CsvOutput("test/test.csv") as csv_output:
        csv_output.write_rows(csv_rows)
