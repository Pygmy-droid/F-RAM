"""The supervisor must not create its scratch outputs inside a source tree."""

import sys
from pathlib import Path

import pytest

from scripts.run_production_memory_gate import main


@pytest.mark.parametrize("relationship", ["inside", "ancestor", "same"])
def test_source_overlap_rejected_before_any_write(tmp_path, monkeypatch, relationship):
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "keep.bin"
    sentinel.write_bytes(b"original")
    root = {
        "inside": source / "run",
        "ancestor": tmp_path,
        "same": source,
    }[relationship]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_production_memory_gate",
            "--repo",
            str(Path(__file__).parents[1]),
            "--source",
            str(source),
            "--run-root",
            str(root),
            "--evaluation-time",
            "2026-09-10T12:00:00Z",
        ],
    )
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2
    assert sorted(source.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"original"
    assert sorted(tmp_path.iterdir()) == [source]
