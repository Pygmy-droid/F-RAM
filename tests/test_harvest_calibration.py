import json
from pathlib import Path
import runpy


def test_harvest_calibration_appends_records(tmp_path, capsys):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    queries_path = tmp_path / "queries.txt"
    queries_path.write_text(
        "What is the F-RAM roadmap vision?\n"
        "Summarize OrthoRoute+ confidence calibration.\n",
        encoding="utf-8",
    )

    json_out = tmp_path / "run.json"

    module = runpy.run_path("scripts/harvest_calibration.py")
    exit_code = module["main"](
        [
            "--storage-root",
            str(storage_root),
            "--queries",
            str(queries_path),
            "--reads",
            "2",
            "--quiet",
            "--json-out",
            str(json_out),
        ]
    )

    assert exit_code == 0

    obs_dir = storage_root / "observability"
    log_path = obs_dir / "calibration.jsonl"
    assert log_path.exists()

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["records_added"] >= 2
    assert Path(payload["calibration_log"]) == log_path
    assert len(payload["runs"]) == 2

    summary = capsys.readouterr().out
    assert "Calibration records appended" in summary
