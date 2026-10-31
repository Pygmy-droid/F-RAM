from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "cathedral_nav.py"
MAP = ROOT / "experiments" / "cosmic_cathedral" / "cosmic-cathedral-map.json"


def _load():
    spec = importlib.util.spec_from_file_location("cathedral_nav_module", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(module, *argv) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = module.main(list(argv))
    return code, buf.getvalue()


def test_map_loads_and_now_reports_cards() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    assert "hearth" in c.nodes
    r = c.now()
    assert r["summary"]["nodes"] == len(c.nodes)
    assert all(n["work_state"] == "in_progress" for n in r["in_progress"])
    assert all(n["work_state"] == "not_started" for n in r["next"])


def test_resolve_accepts_id_card_path_and_label() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    assert c.resolve("hearth") == "hearth"
    assert c.resolve("WB-0001") == "wb-0001"
    assert c.resolve("fram_serving/app.py") == "m:fram_serving/app.py"
    assert c.resolve("fram_serving\\app.py") == "m:fram_serving/app.py"
    assert c.resolve("The Hearth") == "hearth"
    assert c.resolve("definitely-not-a-node-xyz") is None


def test_path_finds_a_route_from_the_hearth_to_a_module() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    steps = c.path("hearth", "m:fram_core/pipeline.py")
    assert steps, "no route from the Hearth to the retrieval core"
    assert steps[-1][1] == "m:fram_core/pipeline.py"
    assert len(steps) <= 6


def test_near_grows_with_depth_and_is_reachable_from_cli() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    one = c.within("workbook", 1)
    two = c.within("workbook", 2)
    assert len(two) >= len(one) > 1
    code, out = _run(module, "--json", "near", "workbook", "--depth", "1")
    assert code == 0
    rows = json.loads(out)
    assert any(r["id"] == "workbook" and r["hops"] == 0 for r in rows)


def test_pipeline_view_lists_modules_and_tests() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    r = c.pipeline("pl-lived")
    assert r and r["pipeline"]["id"] == "pl-lived"
    assert any(m["path"] == "fram_serving/lived_memory.py" for m in r["modules"])
    assert all(t["kind"] == "test" for t in r["tests"])
    assert c.pipeline("hearth") is None


def test_find_ranks_exact_label_first_and_invents_nothing() -> None:
    module = _load()
    c = module.Cathedral(MAP)
    hits = c.find("Workbook")
    assert hits and hits[0][1]["id"] == "workbook"
    code, out = _run(module, "find", "zzqx-nothing-here")
    assert code == 0 and "nothing invented" in out
