from __future__ import annotations

import importlib.util
import json
import pytest
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools" / "codebase_graph.py"


def _load():
    spec = importlib.util.spec_from_file_location("codebase_graph_module", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_tracked_python_file_lands_in_exactly_one_pipeline() -> None:
    module = _load()
    graph = module.build_graph()
    files = module.tracked_python()
    assert graph["files"] == len(files)
    paths = [m["path"] for m in graph["modules"]]
    assert sorted(paths) == files
    assert len(set(paths)) == len(paths)
    pipeline_ids = {p["id"] for p in graph["pipelines"]}
    for m in graph["modules"]:
        assert m["pipeline"] in pipeline_ids, m["path"]
        assert m["layer"] in set(graph["layers"]) | {"evidence"}, m["path"]
        assert (m["layer"] == "evidence") == m["is_test"], m["path"]
    listed = {f for p in graph["pipelines"] for f in p["files"] + p["tests"]}
    assert listed == set(paths)


def test_this_file_and_the_graph_tool_are_placed_sensibly() -> None:
    module = _load()
    graph = module.build_graph()
    by_path = {m["path"]: m for m in graph["modules"]}
    # only tracked files are in the graph, by design
    assert by_path["tools/build_cosmic_cathedral.py"]["pipeline"] == "pl-cathedral"
    assert by_path["tools/workbook.py"]["pipeline"] == "pl-cathedral"
    assert by_path["fram_core/pipeline.py"]["pipeline"] == "pl-orthoroute"
    assert by_path["fram_serving/app.py"]["pipeline"] == "pl-query-serving"
    assert by_path["fram_serving/lived_memory.py"]["pipeline"] == "pl-lived"
    assert by_path["fram_serving/mcp_server.py"]["pipeline"] == "pl-mcp"
    assert by_path["fram_layout/code_chunker.py"]["pipeline"] == "pl-layout"
    assert by_path["tests/test_workbook.py"]["is_test"]


def test_import_edges_resolve_and_never_self_reference() -> None:
    module = _load()
    graph = module.build_graph()
    paths = {m["path"] for m in graph["modules"]}
    assert graph["edges"], "no import edges found"
    for e in graph["edges"]:
        assert e["source"] in paths and e["target"] in paths, e
        assert e["source"] != e["target"], e
        assert e["kind"] in {"imports", "tests"}
    # the Cathedral builder imports the workbook by path, not statically, so no edge; app.py imports config
    assert {"source": "fram_serving/app.py", "target": "fram_serving/config.py", "kind": "imports"} in graph["edges"]


def test_history_is_attached_and_graph_is_deterministic() -> None:
    module = _load()
    a = module.build_graph()
    b = module.build_graph()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    with_history = [m for m in a["modules"] if m["commits"] > 0]
    assert len(with_history) >= 0.9 * len(a["modules"])
    # The shape assertions below describe the full private history (2025-09 onward).
    # A clean public export has one commit; the graph is still valid there.
    commits = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or 0)
    if commits < 50:
        pytest.skip(f"history-shape assertions need the full history; this checkout has {commits} commit(s)")
    first = next(m for m in a["modules"] if m["path"] == "fram_serving/app.py")
    assert first["first_commit"]["date"] <= "2025-09-10"
    assert first["era"] == "I. Retrieval core"
    for p in a["pipelines"]:
        assert p["first_commit"] is None or p["first_commit"]["date"] <= (p["last_commit"] or p["first_commit"])["date"]


def test_pipelines_markdown_renders_every_pipeline(tmp_path: Path) -> None:
    module = _load()
    graph = module.build_graph()
    out = tmp_path / "g.json"
    md = tmp_path / "PIPELINES.md"
    module.write_outputs(graph, out, md)
    text = md.read_text(encoding="utf-8")
    for p in graph["pipelines"]:
        assert p["label"] in text
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "fram.codebase-graph"
