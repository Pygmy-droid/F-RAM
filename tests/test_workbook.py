from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "workbook.py"


def _load():
    spec = importlib.util.spec_from_file_location("workbook_module", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def wb(tmp_path: Path):
    module = _load()
    return module, module.Workbook(tmp_path)


def test_add_start_finish_and_render(wb, tmp_path: Path) -> None:
    module, book = wb
    a = book.add("First seam", "why it matters", files=["tools/x.py"], actor="Wren Holloway")
    b = book.add("Second seam", actor="Wren Holloway")
    assert (a, b) == ("WB-0001", "WB-0002")
    book.set_state(a, "in_progress", actor="Wren Holloway")
    book.note(a, "learned something", actor="Rick")
    st = book.render()
    assert st.cards[a].state == "in_progress"
    assert st.cards[a].started
    assert st.rank(a) == 1 and st.rank(b) == 2
    text = (tmp_path / "workbook" / "WORKBOOK.md").read_text(encoding="utf-8")
    assert "## In progress (1)" in text and "WB-0001" in text and "learned something" in text
    status = (tmp_path / "workbook" / "STATUS.md").read_text(encoding="utf-8")
    assert "## Now" in status and "WB-0001" in status
    book.set_state(a, "finished")
    st = book.render()
    assert st.cards[a].finished
    assert book.check(strict=True)["ok"]


def test_state_transitions_are_guarded(wb) -> None:
    module, book = wb
    a = book.add("Only card")
    with pytest.raises(module.WorkbookError):
        book.set_state(a, "not_started")  # already there
    with pytest.raises(module.WorkbookError):
        book.set_state(a, "sideways")
    book.set_state(a, "finished")
    with pytest.raises(module.WorkbookError):
        book.set_state(a, "not_started")  # finished cannot jump back to not started
    book.set_state(a, "in_progress")  # reopen is allowed
    assert book.state().cards[a].finished is None


def test_priority_moves_keep_ranks_unique_and_gapless(wb) -> None:
    module, book = wb
    ids = [book.add(f"Card {i}") for i in range(1, 5)]
    book.priority(ids[3], 1)
    st = book.state()
    assert st.order == [ids[3], ids[0], ids[1], ids[2]]
    book.priority(ids[0], 99)  # beyond the end lands last
    st = book.state()
    assert st.order[-1] == ids[0]
    assert sorted(st.rank(c) for c in ids) == [1, 2, 3, 4]
    c = book.add("Inserted at two", priority=2)
    assert book.state().rank(c) == 2


def test_chain_tamper_is_detected_and_blocks_appends(wb, tmp_path: Path) -> None:
    module, book = wb
    book.add("A")
    book.add("B")
    path = tmp_path / "workbook" / "EVENTS.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["data"]["title"] = "Edited"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = book.check()
    assert not report["ok"]
    assert any("hash does not match" in e for e in report["errors"])
    with pytest.raises(module.WorkbookError):
        book.add("C")


def test_strict_check_catches_stale_render(wb, tmp_path: Path) -> None:
    module, book = wb
    book.add("A")
    book.render()
    assert book.check(strict=True)["ok"]
    book.set_state("WB-0001", "in_progress")  # no render afterwards
    report = book.check(strict=True)
    assert not report["ok"]
    assert any("stale" in e for e in report["errors"])
    assert book.check(strict=False)["ok"]


def test_render_is_deterministic(wb, tmp_path: Path) -> None:
    module, book = wb
    book.add("A", "desc")
    book.set_state("WB-0001", "in_progress")
    st = book.state()
    assert book.render_workbook(st) == book.render_workbook(book.state())
    assert book.render_status(st) == book.render_status(book.state())


def test_autolog_attaches_commits_that_name_a_card(tmp_path: Path) -> None:
    module = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.com"]
    subprocess.run(git + ["init", "-q"], check=True)
    book = module.Workbook(repo)
    book.add("Tracked work")
    (repo / "f.txt").write_text("1", encoding="utf-8")
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "work on WB-0001: first slice"], check=True)
    (repo / "f.txt").write_text("2", encoding="utf-8")
    subprocess.run(git + ["commit", "-q", "-am", "unrelated"], check=True)
    added = book.autolog()
    assert len(added) == 1 and added[0][1] == "WB-0001"
    assert book.autolog() == []  # idempotent
    st = book.state()
    assert st.cards["WB-0001"].commits[0]["subject"].startswith("work on WB-0001")
    assert book.check()["ok"]


def test_cli_round_trip(tmp_path: Path) -> None:
    module = _load()
    root = str(tmp_path)
    assert module.main(["--root", root, "--actor", "Wren", "add", "CLI card", "--desc", "d"]) == 0
    assert module.main(["--root", root, "--actor", "Wren", "start", "wb-0001"]) == 0
    assert module.main(["--root", root, "check", "--strict"]) == 0
    assert module.main(["--root", root, "list"]) == 0
    assert module.main(["--root", root, "start", "WB-0001"]) == 2  # already in progress
