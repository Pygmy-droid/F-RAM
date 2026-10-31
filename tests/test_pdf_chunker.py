from pathlib import Path

import pytest

from fram_layout.pdf_chunker import chunk_pdf, to_snippet_dicts
from fram_layout.assembler import assemble


def _write(lines):
    path = Path('tests/data/sample_pdf.txt')
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path


def test_chunk_pdf_emits_hierarchy(tmp_path):
    path = tmp_path / 'doc.txt'
    path.write_text('line1\nline2\nline3\nline4', encoding='utf-8')
    snippets = chunk_pdf(path)
    assert len(snippets) == 4
    first = snippets[0]
    assert first.hierarchy['segment'].startswith('page:0')


def test_pdf_snippets_assemble_with_segments(tmp_path):
    lines = [f'line {i}' for i in range(12)]
    path = tmp_path / 'doc.txt'
    path.write_text('\n'.join(lines), encoding='utf-8')
    snippets = to_snippet_dicts(chunk_pdf(path))
    assembled = assemble(snippets)
    assert '[doc:0 :: page:0:region:0]' in assembled
    assert 'line 0' in assembled
    assert '[doc:0 :: page:0:region:1]' in assembled


def test_pdf_chunker_deterministic_output(tmp_path):
    path = tmp_path / "doc.txt"
    lines = ["# Intro", "Line A", "## Details", "Line B"]
    path.write_text("\n".join(lines), encoding="utf-8")

    first = chunk_pdf(path)
    second = chunk_pdf(path)
    assert [s.text for s in first] == [s.text for s in second]
    assert [s.hierarchy for s in first] == [s.hierarchy for s in second]


def test_pdf_chunker_column_order_fallback(tmp_path):
    path = tmp_path / "doc.txt"
    lines = ["L|Left 1", "L|Left 2", "R|Right 1", "R|Right 2"]
    path.write_text("\n".join(lines), encoding="utf-8")

    snippets = chunk_pdf(path)
    assert [s.text for s in snippets] == ["Left 1", "Left 2", "Right 1", "Right 2"]
    assert all(not s.layout_uncertain for s in snippets)


def test_pdf_chunker_heading_section_path(tmp_path):
    path = tmp_path / "doc.txt"
    lines = ["# Intro", "Line A", "## Details", "Line B"]
    path.write_text("\n".join(lines), encoding="utf-8")

    snippets = chunk_pdf(path)
    line_a = next(snippet for snippet in snippets if snippet.text == "Line A")
    line_b = next(snippet for snippet in snippets if snippet.text == "Line B")
    assert line_a.hierarchy.get("section") == "intro"
    assert line_b.hierarchy.get("section") == "intro/details"
