import io

from fram_layout import table_chunker, assembler
from fram_core.claims import extract_table_claims, ClaimType


def _sample_csv() -> io.StringIO:
    return io.StringIO("Item,Price,Qty\nWidget,12,5\nGadget,9,12\n")


def test_read_csv_to_table_and_window_header():
    table = table_chunker.read_csv_to_table(_sample_csv())
    assert table["headers"] == ["Item", "Price", "Qty"]
    assert table["rows"][0] == ["Widget", "12", "5"]

    snippet = table_chunker.window_for_cell(table, row_index=1, col_index=0)
    lines = snippet.splitlines()
    assert lines[0] == "Item | Price | Qty"
    assert "Gadget" in lines[-1]


def test_extract_table_claims_includes_header_context():
    table = table_chunker.read_csv_to_table(_sample_csv())
    claims = extract_table_claims(table["rows"], table["headers"])
    keys = {c.key for c in claims if c.type == ClaimType.TableFact}
    assert "Price=12" in keys
    assert any(c.ctx == {"row": 0, "col": 1, "col_header": "Price"} for c in claims)


def test_assembler_places_header_before_cell_line():
    table = table_chunker.read_csv_to_table(_sample_csv())
    snippet = assembler.assemble(
        [
            {
                "kind": "table_cell",
                "headers": table["headers"],
                "row": table["rows"][0],
            }
        ]
    )
    lines = snippet.splitlines()
    assert lines[0] == "Item | Price | Qty"
    assert lines[1] == "Widget | 12 | 5"
