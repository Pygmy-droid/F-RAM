from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_META = PROJECT_ROOT / "storage" / "observability" / "calibration_latest.json"
STEP_ORDER = ["harvest", "slice", "fit", "lint", "status"]


@dataclass
class StepResult:
    status: str
    exit_code: int | None
    reason: str | None
    started_at: float
    finished_at: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "reason": self.reason,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started_at)),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.finished_at)),
        }


def _run_subprocess(args: List[str], timeout: float | None = None) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    stderr = (proc.stderr or "").strip()
    return proc.returncode, stderr


def _step_harvest(timeout: float | None = None) -> tuple[int, str]:
    script = PROJECT_ROOT / "scripts" / "harvest_calibration.py"
    return _run_subprocess([sys.executable, str(script)], timeout=timeout)


def _step_slice(timeout: float | None = None) -> tuple[int, str]:
    script = PROJECT_ROOT / "tools" / "calibration_filter.py"
    return _run_subprocess([sys.executable, str(script)], timeout=timeout)


def _step_fit(timeout: float | None = None) -> tuple[int, str]:
    script = PROJECT_ROOT / "scripts" / "calibrate_confidence.py"
    return _run_subprocess([sys.executable, str(script)], timeout=timeout)


def _step_lint(timeout: float | None = None) -> tuple[int, str]:
    script = PROJECT_ROOT / "tools" / "calibration_lint.py"
    return _run_subprocess([sys.executable, str(script)], timeout=timeout)


def _step_status(timeout: float | None = None) -> tuple[int, str]:
    script = PROJECT_ROOT / "tools" / "calibration_status.py"
    return _run_subprocess([sys.executable, str(script), "--json"], timeout=timeout)


STEP_FUNCS: Dict[str, Callable[[float | None], tuple[int, str]]] = {
    "harvest": _step_harvest,
    "slice": _step_slice,
    "fit": _step_fit,
    "lint": _step_lint,
    "status": _step_status,
}


def _atomic_write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass
    os.replace(tmp, path)


def run_pipeline(
    steps: Sequence[str],
    *,
    dry_run: bool = False,
    output_meta: Path = DEFAULT_META,
    max_runtime_seconds: float | None = None,
) -> Dict[str, object]:
    run_started = time.time()
    step_results: Dict[str, StepResult] = {}
    failure = False
    elapsed_start = run_started
    for name in steps:
        started = time.time()
        if dry_run:
            step_results[name] = StepResult("skipped_dry_run", None, None, started, time.time())
            continue
        if failure:
            step_results[name] = StepResult("skipped_due_to_failure", None, None, started, time.time())
            continue
        runner = STEP_FUNCS.get(name)
        if runner is None:
            step_results[name] = StepResult("failed", 127, "unknown_step", started, time.time())
            failure = True
            continue
        timeout_remaining = None
        if max_runtime_seconds is not None:
            elapsed = time.time() - run_started
            timeout_remaining = max(0, max_runtime_seconds - elapsed)
        try:
            code, stderr = runner(timeout_remaining if timeout_remaining and timeout_remaining > 0 else None)
        except Exception as exc:  # pragma: no cover - defensive
            step_results[name] = StepResult("failed", 1, str(exc), started, time.time())
            failure = True
            continue
        status = "ok" if code == 0 else "failed"
        if status != "ok":
            failure = True
        step_results[name] = StepResult(status, code, stderr or None, started, time.time())
        if failure:
            # Do not break; downstream will be marked skipped_due_to_failure in loop
            pass
    run_finished = time.time()
    summary = {
        "run_started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(run_started)),
        "run_finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(run_finished)),
        "dry_run": dry_run,
        "max_runtime_seconds": max_runtime_seconds,
        "steps": {k: v.to_dict() for k, v in step_results.items()},
        "last_result": "failed" if failure else "ok",
        "total_duration_seconds": round(run_finished - run_started, 3),
    }
    _atomic_write_json(output_meta, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run calibration pipeline (harvest -> slice -> fit -> lint -> status)")
    parser.add_argument("--steps", type=str, help="Comma-separated steps to run (default: harvest,slice,fit,lint,status)")
    parser.add_argument("--dry-run", action="store_true", help="Log intent only; do not execute steps.")
    parser.add_argument("--output-meta", type=Path, default=DEFAULT_META, help="Path for run meta (default: storage/observability/calibration_latest.json)")
    parser.add_argument("--max-runtime-seconds", type=float, help="Optional overall timeout safety fuse.")
    args = parser.parse_args(argv)

    if args.steps:
        requested = [s.strip() for s in args.steps.split(",") if s.strip()]
        steps = [s for s in requested if s in STEP_ORDER]
        if not steps:
            steps = STEP_ORDER
    else:
        steps = STEP_ORDER

    summary = run_pipeline(
        steps,
        dry_run=args.dry_run,
        output_meta=args.output_meta,
        max_runtime_seconds=args.max_runtime_seconds,
    )
    if summary["last_result"] == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
