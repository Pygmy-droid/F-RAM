from __future__ import annotations

from pathlib import Path
import runpy

import tools.calibration_run as calib_run


def test_calibration_run_happy(monkeypatch, tmp_path: Path):
    calls = []

    def ok_step(timeout=None):
        calls.append(timeout)
        return 0, ""

    for name in calib_run.STEP_ORDER:
        monkeypatch.setitem(calib_run.STEP_FUNCS, name, ok_step)
    meta_path = tmp_path / "calibration_latest.json"
    summary = calib_run.run_pipeline(calib_run.STEP_ORDER, dry_run=False, output_meta=meta_path)
    assert meta_path.exists()
    assert summary["last_result"] == "ok"
    assert all(step["status"] == "ok" for step in summary["steps"].values())


def test_calibration_run_failure(monkeypatch, tmp_path: Path):
    def fail_step(timeout=None):
        return 1, "boom"

    monkeypatch.setitem(calib_run.STEP_FUNCS, "harvest", fail_step)
    for name in calib_run.STEP_ORDER[1:]:
        monkeypatch.setitem(calib_run.STEP_FUNCS, name, lambda timeout=None: (0, ""))
    meta_path = tmp_path / "calibration_latest.json"
    summary = calib_run.run_pipeline(calib_run.STEP_ORDER, dry_run=False, output_meta=meta_path)
    assert summary["steps"]["harvest"]["status"] == "failed"
    assert summary["steps"]["slice"]["status"] == "skipped_due_to_failure"
    assert summary["last_result"] == "failed"


def test_calibration_run_dry(monkeypatch, tmp_path: Path):
    called = False

    def mark(timeout=None):
        nonlocal called
        called = True
        return 0, ""

    for name in calib_run.STEP_ORDER:
        monkeypatch.setitem(calib_run.STEP_FUNCS, name, mark)
    meta_path = tmp_path / "calibration_latest.json"
    summary = calib_run.run_pipeline(["fit", "status"], dry_run=True, output_meta=meta_path)
    assert called is False
    assert summary["steps"]["fit"]["status"] == "skipped_dry_run"
    assert summary["steps"]["status"]["status"] == "skipped_dry_run"
    assert summary["last_result"] == "ok"


def test_calibration_run_subset(monkeypatch, tmp_path: Path):
    steps = ["fit", "status"]
    for name in steps:
        monkeypatch.setitem(calib_run.STEP_FUNCS, name, lambda timeout=None: (0, ""))
    meta_path = tmp_path / "calibration_latest.json"
    summary = calib_run.run_pipeline(steps, dry_run=False, output_meta=meta_path)
    assert set(summary["steps"].keys()) == set(steps)
    assert all(step["status"] == "ok" for step in summary["steps"].values())


def test_atomic_meta(tmp_path: Path):
    meta_path = tmp_path / "calibration_latest.json"
    payload = {"last_result": "ok"}
    calib_run._atomic_write_json(meta_path, payload)
    content = meta_path.read_text(encoding="utf-8")
    assert content.strip().startswith("{") and content.strip().endswith("}")
