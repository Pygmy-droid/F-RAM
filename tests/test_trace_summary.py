from __future__ import annotations

import json

from fram_serving import observability
from tools import trace_summary


def _make_record(decision: str = "anchors", coverage_delta: float = 1.5) -> dict:
    return {
        "id": "test-trace",
        "query": "summary check",
        "citations": ["docs:file:chunk1"],
        "trace": {
            "confidence": {"decision": decision},
            "coverage": {
                "delta_total": coverage_delta,
                "delta_by_stage": {"anchors": coverage_delta},
                "budgets": {"reads": 1.0, "tokens": 0.0, "pairs": 0.0, "cost": 0.0},
            },
            "selection": {
                "coverage_delta": {"total": coverage_delta},
                "budgets": {"reads": 1.0, "tokens": 0.0, "pairs": 0.0, "cost": 0.0},
            },
            "memory": {"status": "active", "available": 0, "used": 0},
        },
    }


def test_trace_summary_cli_stdout(tmp_path, capsys):
    traces_dir = tmp_path / "traces"
    writer = observability.TraceLogWriter(traces_dir, daily_rollover=False)
    writer.write(_make_record())

    exit_code = trace_summary.main(["--storage-root", str(tmp_path), "--limit", "5"])
    assert exit_code == 0

    output = capsys.readouterr().out
    summary = json.loads(output)
    assert summary["summary"]["total_traces"] == 1
    assert summary["summary"]["decisions"]["anchors"] == 1


def test_trace_summary_json_out(tmp_path):
    traces_dir = tmp_path / "custom_traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    writer = observability.TraceLogWriter(traces_dir, daily_rollover=False)
    writer.write(_make_record(decision="local", coverage_delta=2.0))

    out_path = tmp_path / "summary.json"
    exit_code = trace_summary.main(
        [
            "--storage-root",
            str(tmp_path),
            "--traces-dir",
            str(traces_dir),
            "--include-records",
            "--json-out",
            str(out_path),
        ]
    )
    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["summary"]["total_traces"] == 1
    assert data["summary"]["decisions"]["local"] == 1
    assert data["records"], "expected records to be included"
