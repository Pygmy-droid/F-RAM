import json
import runpy
from pathlib import Path


SAMPLES = [
    {
        "time": "2025-09-28T10:00:00+00:00",
        "doc_id": "doc_a",
        "chunk_id": 1,
        "label": 1,
        "decision": "local",
        "prob": 0.9,
        "features": {"Delta_d_z": 1.0},
        "query": "roadmap question",
        "domain": "roadmap",
        "task": "qa",
        "budget_reads": 4,
    },
    {
        "time": "2025-09-28T11:00:00+00:00",
        "doc_id": "doc_b",
        "chunk_id": 2,
        "label": 0,
        "decision": "global",
        "prob": 0.1,
        "features": {"Delta_d_z": -1.0},
        "query": "diary recap",
        "domain": "diary",
        "task": "summary",
        "budget_reads": 3,
    },
    {
        "time": "2025-09-28T12:00:00+00:00",
        "doc_id": "doc_c",
        "chunk_id": 3,
        "label": 1,
        "decision": "anchors",
        "prob": 0.6,
        "features": {"Delta_d_z": 2.0},
        "query": "generic",
        "task": "qa",
        "budget_reads": 2,
    },
]


def _write_log(path: Path) -> None:
    lines = "\n".join(json.dumps(item, ensure_ascii=False) for item in SAMPLES)
    path.write_text(lines + "\n", encoding="utf-8")


def test_calibration_filter_summary(tmp_path, capsys):
    log_path = tmp_path / "calibration.jsonl"
    _write_log(log_path)

    module = runpy.run_path("tools/calibration_filter.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--include-records",
    ])
    assert exit_code == 0

    data = json.loads(capsys.readouterr().out)
    summary = data["summary"]
    assert summary["total"] == 3
    assert summary["positive"] == 2
    assert summary["by_domain"]["roadmap"] == 1
    assert summary["by_domain"]["diary"] == 1
    assert summary["by_domain"]["unknown"] == 1
    assert len(data["records"]) == 3


def test_calibration_filter_with_filters(tmp_path, capsys):
    log_path = tmp_path / "calibration.jsonl"
    _write_log(log_path)

    module = runpy.run_path("tools/calibration_filter.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--domain",
        "roadmap",
        "--after",
        "2025-09-28T09:59:59+00:00",
        "--before",
        "2025-09-28T10:30:00+00:00",
    ])
    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["total"] == 1
    assert data["summary"]["by_decision"]["local"]["count"] == 1


def test_calibration_filter_json_out(tmp_path):
    log_path = tmp_path / "calibration.jsonl"
    _write_log(log_path)
    out_path = tmp_path / "summary.json"

    module = runpy.run_path("tools/calibration_filter.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--task",
        "summary",
        "--json-out",
        str(out_path),
    ])
    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 1
    assert payload["filters"]["task"] == ["summary"]
