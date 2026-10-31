from pathlib import Path

from fram_layout.table_chunker import read_csv_to_table, window_for_cell


def test_table_window_includes_headers(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("Name,Value\nAlpha,1\nBeta,2\n", encoding="utf-8")
    table = read_csv_to_table(path)
    snippet = window_for_cell(table, row_index=0, col_index=0)
    lines = snippet.splitlines()
    assert lines[0] == "Name | Value"
    assert "Alpha | 1" in lines


def test_table_window_preserves_row_order(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("Name,Value\nAlpha,1\nBeta,2\nGamma,3\n", encoding="utf-8")
    table = read_csv_to_table(path)
    snippet = window_for_cell(table, row_index=1, col_index=0, k_rows=1)
    lines = snippet.splitlines()
    assert lines[1] == "Alpha | 1"
    assert lines[2] == "Beta | 2"
    assert lines[3] == "Gamma | 3"
