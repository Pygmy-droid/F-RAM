import json
import subprocess
import sys
from pathlib import Path


CALIBRATION_TEMPLATE = {
    "logistic_coefs": {"a": 0.1, "b": 0.2, "c": 0.3, "g": 0.1, "h": 0.4, "d": 0.0},
    "temperature": 1.0,
    "tau1": 0.9,
    "tau2": 0.6,
}


def _write_payload(path: Path, **updates) -> Path:
    payload = dict(CALIBRATION_TEMPLATE)
    payload.update(updates)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _prepare_layout(tmp_path: Path) -> Path:
    index_dir = tmp_path / "index" / "demo_corpus"
    index_dir.mkdir(parents=True, exist_ok=True)
    _write_payload(index_dir / "calibration.json", tau1=0.85, tau2=0.55)
    _write_payload(index_dir / "calibration_roadmap.json", tau1=0.92, tau2=0.7)
    _write_payload(index_dir / "calibration_task_diary.json", tau1=0.88, tau2=0.65)
    return index_dir


def test_calibration_status_text(tmp_path):
    _prepare_layout(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/calibration_status.py",
            "--storage-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    stdout = result.stdout
    assert "Global: tau1=0.8500" in stdout
    assert "- roadmap:" in stdout
    assert "- diary:" in stdout


def test_calibration_status_json(tmp_path):
    _prepare_layout(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "tools/calibration_status.py",
            "--storage-root",
            str(tmp_path),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["default_domain"] == "general"
    assert payload["default_task"] == "qa"
    assert payload["global"]["tau1"] == 0.85
    assert payload["domains"]["roadmap"]["tau2"] == 0.7
    assert payload["tasks"]["diary"]["tau1"] == 0.88


def test_calibration_status_reports_missing_payloads(tmp_path):
    index_dir = tmp_path / "index" / "demo_corpus"
    index_dir.mkdir(parents=True, exist_ok=True)
    _write_payload(index_dir / "calibration.json", tau1=0.87, tau2=0.57)

    text_run = subprocess.run(
        [
            sys.executable,
            "tools/calibration_status.py",
            "--storage-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert text_run.returncode == 0
    assert "- roadmap: <missing>" in text_run.stdout
    assert "- diary: <missing>" in text_run.stdout

    json_run = subprocess.run(
        [
            sys.executable,
            "tools/calibration_status.py",
            "--storage-root",
            str(tmp_path),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert json_run.returncode == 0
    summary = json.loads(json_run.stdout)
    assert summary["domains"]["roadmap"] is None
    assert summary["tasks"]["diary"] is None
