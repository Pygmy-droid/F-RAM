import json
from pathlib import Path
import runpy


SAMPLES = [
    {
        "time": "2025-09-25T12:18:29.883538+00:00",
        "doc_id": "docs_ingest_f_ram_roadmap.txt",
        "chunk_id": 4,
        "label": 1,
        "decision": "local",
        "prob": 0.9,
        "features": {"Delta_d_z": 10.0},
        "query": "What is the roadmap vision?",
    },
    {
        "time": "2025-09-25T12:19:00+00:00",
        "doc_id": "docs_ingest_framv2_2_spec.txt",
        "chunk_id": 18,
        "label": 1,
        "decision": "global",
        "prob": 0.2,
        "features": {"Delta_d_z": -2.0},
        "query": "Summarize key spec decisions",
        "domain": "general",
        "task": "qa",
        "budget_reads": 2,
    },
    {
        "time": "2025-09-26T09:12:00+00:00",
        "doc_id": "docs_ingest_diary_entry.txt",
        "chunk_id": 2,
        "label": 1,
        "decision": "local",
        "prob": 0.7,
        "features": {"Delta_d_z": 5.0},
        "query": "Daily diary recap",
    },
    {
        "time": "2025-09-26T10:00:00+00:00",
        "doc_id": "docs_ingest_misc.txt",
        "chunk_id": 7,
        "label": 0,
        "decision": "anchors",
        "prob": 0.4,
        "features": {"Delta_d_z": 1.5},
        "query": "Explain FRAM config defaults",
    },
]


def _write_log(path: Path) -> None:
    lines = "\n".join(json.dumps(item, ensure_ascii=False) for item in SAMPLES)
    path.write_text(lines + "\n", encoding="utf-8")


def test_backfill_writes_defaults(tmp_path, capsys):
    log_path = tmp_path / "calibration.jsonl"
    out_path = tmp_path / "out.jsonl"
    _write_log(log_path)

    module = runpy.run_path("tools/calibration_backfill.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--output",
        str(out_path),
        "--default-budget",
        "5",
        "--infer-domain",
        "--overwrite-domain",
        "--infer-task",
        "--overwrite-task",
    ])
    assert exit_code == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["total"] == len(SAMPLES)
    assert summary["updated"] == len(SAMPLES)
    assert summary["domain_set"] == 4
    assert summary["domain_inferred"] == 3
    assert summary["domain_defaulted"] == 1
    assert summary["domain_overwritten"] == 1
    assert summary["task_set"] == 4
    assert summary["task_inferred"] == 2
    assert summary["task_defaulted"] == 2
    assert summary["task_overwritten"] == 1
    assert summary["budget_set"] == 3

    records = [
        json.loads(line)
        for line in out_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert records[0]["domain"] == "roadmap"
    assert records[0]["task"] == "qa"
    assert records[0]["budget_reads"] == 5

    assert records[1]["domain"] == "spec"
    assert records[1]["task"] == "summary"
    assert records[1]["budget_reads"] == 2

    assert records[2]["domain"] == "diary"
    assert records[2]["task"] == "summary"
    assert records[2]["budget_reads"] == 5

    assert records[3]["domain"] == "general"
    assert records[3]["task"] == "qa"
    assert records[3]["budget_reads"] == 5


def test_backfill_dry_run(tmp_path, capsys):
    log_path = tmp_path / "calibration.jsonl"
    _write_log(log_path)
    original = log_path.read_text(encoding="utf-8")

    module = runpy.run_path("tools/calibration_backfill.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--dry-run",
        "--infer-domain",
        "--infer-task",
    ])
    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["total"] == len(SAMPLES)
    assert log_path.read_text(encoding="utf-8") == original


def test_backfill_in_place_with_backup(tmp_path):
    log_path = tmp_path / "calibration.jsonl"
    backup_path = tmp_path / "backup.jsonl"
    _write_log(log_path)

    module = runpy.run_path("tools/calibration_backfill.py")
    exit_code = module["main"]([
        "--log",
        str(log_path),
        "--default-domain",
        "general",
        "--default-task",
        "qa",
        "--default-budget",
        "4",
        "--infer-domain",
        "--overwrite-domain",
        "--infer-task",
        "--overwrite-task",
        "--overwrite-budget",
        "--backup",
        str(backup_path),
    ])
    assert exit_code == 0

    backup_content = backup_path.read_text(encoding="utf-8")
    assert backup_content.startswith("{")

    updated_records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert updated_records[0]["domain"] == "roadmap"
    assert updated_records[0]["budget_reads"] == 4
    assert updated_records[1]["domain"] == "spec"
    assert updated_records[1]["task"] == "summary"
    assert updated_records[1]["budget_reads"] == 4
    assert updated_records[2]["domain"] == "diary"
    assert updated_records[2]["task"] == "summary"
