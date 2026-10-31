from __future__ import annotations

from pathlib import Path

from tools.refactor_checklist import export_checklist


def test_refactor_checklist_export(tmp_path: Path) -> None:
    out_path = tmp_path / "checklist.md"
    export_checklist(out_path)
    content = out_path.read_text(encoding="utf-8")
    assert "Weekly Refactor Checklist" in content
    assert "[ ]" in content
