from fram_layout.assembler import assemble


def test_assemble_groups_by_segment():
    snippets = [
        {
            "kind": "text",
            "text": "Alpha intro",
            "hierarchy": {"cluster": "doc:alpha", "segment": "seg:alpha-0"},
        },
        {
            "kind": "text",
            "text": "Alpha detail",
            "hierarchy": {"cluster": "doc:alpha", "segment": "seg:alpha-0"},
        },
        {
            "kind": "text",
            "text": "Beta intro",
            "hierarchy": {"cluster": "doc:beta", "segment": "seg:beta-1"},
        },
        {
            "kind": "table_cell",
            "headers": ["Col1", "Col2"],
            "row": ["A", "B"],
            "hierarchy": {"cluster": "doc:beta", "segment": "seg:beta-1"},
        },
    ]

    assembled = assemble(snippets)
    assert "[doc:alpha :: seg:alpha-0]" in assembled
    assert "Alpha intro" in assembled
    assert "Alpha detail" in assembled
    assert "[doc:beta :: seg:beta-1]" in assembled
    assert "Col1 | Col2" in assembled
    assert "A | B" in assembled


def test_assemble_defaults_when_missing_hierarchy():
    snippets = [
        {"kind": "text", "text": "Plain text"},
    ]
    assembled = assemble(snippets)
    assert "[cluster:unknown :: segment:0]" in assembled
    assert "Plain text" in assembled
