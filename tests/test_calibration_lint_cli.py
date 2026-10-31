import json
import subprocess
import sys
from pathlib import Path


CALIBRATION_TEMPLATE = {
    "tau1": 0.9,
    "tau2": 0.4,
    "temperature": 1.0,
    "logistic_coefs": {"a": 0.1, "b": 0.2, "c": 0.3, "g": 0.4, "h": 0.5, "d": -0.1},
}


def _write_payload(path: Path, **overrides) -> Path:
    payload = dict(CALIBRATION_TEMPLATE)
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_calibration_layout(tmp_path: Path) -> tuple[Path, Path]:
    storage_root = tmp_path / "storage"
    corpus_dir = storage_root / "index" / "demo_corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    log_path = tmp_path / "calibration.jsonl"
    entries = [
        {
            "features": {"Delta_d_z": 0.1, "rho_pos": 0.2, "mhd": 0.3, "d_c_z": 0.4, "fresh": 0.5},
            "label": 1,
        },
        {
            "features": {"Delta_d_z": -0.2, "rho_pos": -0.1, "mhd": 0.05, "d_c_z": -0.3, "fresh": 0.2},
            "label": 0,
        },
    ]
    log_path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return log_path, corpus_dir / "calibration.json"


def test_calibration_lint_pass(tmp_path):
    payload_path = _write_payload(tmp_path / "calibration.json")
    result = subprocess.run(
        [sys.executable, "tools/calibration_lint.py", str(payload_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[OK]" in result.stdout
    assert "tau1=0.9000" in result.stdout


def test_calibration_lint_detects_tau_order(tmp_path):
    payload_path = _write_payload(tmp_path / "calibration.json", tau1=0.8, tau2=0.81)
    result = subprocess.run(
        [sys.executable, "tools/calibration_lint.py", str(payload_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "tau2 must be strictly less than tau1" in result.stdout
    assert "[FAIL]" in result.stdout


def test_calibration_lint_detects_sign_inverting_centroid_distance(tmp_path):
    payload_path = _write_payload(
        tmp_path / "calibration.json",
        logistic_coefs={**CALIBRATION_TEMPLATE["logistic_coefs"], "g": -0.1},
    )
    result = subprocess.run(
        [sys.executable, "tools/calibration_lint.py", str(payload_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "centroid distance cannot increase confidence" in result.stdout


def test_calibration_lint_strict_bounds(tmp_path):
    payload_path = _write_payload(tmp_path / "calibration.json", tau1=1.2)
    result = subprocess.run(
        [sys.executable, "tools/calibration_lint.py", "--strict", str(payload_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "tau1 must be <= 1.0" in result.stdout


def test_calibration_lint_strict_ok(tmp_path):
    payload_path = _write_payload(tmp_path / "calibration.json", tau1=0.95, tau2=0.91)
    result = subprocess.run(
        [sys.executable, "tools/calibration_lint.py", "--strict", str(payload_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[STRICT]" in result.stdout


def test_calibrate_confidence_script_runs_lint_and_status(tmp_path, monkeypatch):
    log_path, out_path = _make_calibration_layout(tmp_path)

    # monkeypatch storage root env so calibrate uses the temporary storage tree
    monkeypatch.setenv("FRAM_STORAGE_ROOT", str(tmp_path / "storage"))

    result = subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_confidence.py",
            "--log",
            str(log_path),
            "--out",
            str(out_path),
            "--lint",
            "--status",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    stdout = result.stdout
    assert "[OK]" in stdout or "[STRICT]" in stdout
    assert "Global: tau1" in stdout

    # status JSON path
    json_result = subprocess.run(
        [
            sys.executable,
            "scripts/calibrate_confidence.py",
            "--log",
            str(log_path),
            "--out",
            str(out_path),
            "--status-json",
        ],
        capture_output=True,
        text=True,
    )
    assert json_result.returncode == 0
    summary = json.loads(json_result.stdout)
    assert summary["global"]["tau1"] > summary["global"]["tau2"]
