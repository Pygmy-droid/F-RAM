"""CSV-backed table helpers aligned with FRAM v2.2 layout spec (§14)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Sequence, TextIO, Union


def _open_csv(source: Union[str, Path, TextIO]) -> Iterable[List[str]]:
    """Yield rows from a CSV path or file-like handle."""

    if hasattr(source, "read"):
        reader = csv.reader(source)  # type: ignore[arg-type]
        return list(reader)

    path = Path(source)
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        return list(reader)


def read_csv_to_table(source: Union[str, Path, TextIO]) -> dict:
    """Parse a CSV file into headers and row lists."""

    rows = list(_open_csv(source))
    if not rows:
        return {"headers": [], "rows": []}

    headers = [cell.strip() for cell in rows[0]]
    data_rows = [[cell.strip() for cell in row] for row in rows[1:]]
    return {"headers": headers, "rows": data_rows}


def _format_row(values: Sequence[str]) -> str:
    return " | ".join(values)


def window_for_cell(
    table: dict,
    row_index: int,
    col_index: int,
    k_rows: int = 1,
) -> str:
    """Return a snippet containing header row plus nearby table rows."""

    headers: Sequence[str] = table.get("headers", [])
    rows: Sequence[Sequence[str]] = table.get("rows", [])
    if row_index < 0 or row_index >= len(rows):
        raise IndexError("row_index out of range")
    if col_index < 0 or (headers and col_index >= len(headers)):
        raise IndexError("col_index out of range")

    start = max(0, row_index - k_rows)
    end = min(len(rows), row_index + k_rows + 1)

    snippet_lines: List[str] = []
    snippet_lines.append(_format_row(headers))
    for idx in range(start, end):
        snippet_lines.append(_format_row(rows[idx]))
    return "\n".join(snippet_lines)
