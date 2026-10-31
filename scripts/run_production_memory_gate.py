"""Supervise bounded, isolated production gate shards and verify their merge.

Run as ``python -m scripts.run_production_memory_gate``. Raw captures stay in
the supplied scratch root. No persistent runtime setting or source is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value) -> None:
    from fram_eval.production_memory_eval import _replace_progress

    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    _replace_progress(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--evaluation-time", required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--half-life-hours", type=float)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be between 1 and 4")
    args.repo = args.repo.resolve()
    args.source = args.source.resolve()
    args.run_root = args.run_root.resolve()
    if not args.source.is_dir():
        parser.error("source must be an existing offline memory directory")
    if args.run_root.is_relative_to(args.source) or args.source.is_relative_to(
        args.run_root
    ):
        parser.error("run root must be disjoint from the source memory directory")
    if not (args.repo / "scripts" / "production_memory_eval.py").is_file():
        parser.error("repo must contain scripts/production_memory_eval.py")
    if args.dataset is not None and not args.dataset.is_file():
        parser.error("dataset must be an existing file")
    if args.config is not None:
        args.config = args.config.resolve()
        if not args.config.is_file():
            parser.error("config must be an existing file")
    if args.timeout_seconds <= 0:
        parser.error("timeout must be positive")
    args.run_root.mkdir(parents=True, exist_ok=False)
    bootstrap = args.run_root / "supervisor-bootstrap"
    os.environ.update(
        {
            "FRAM_STORAGE_ROOT": str(bootstrap),
            "COGMEM_STORAGE_ROOT": str(bootstrap / "memory" / "cognitive"),
            "COGMEM_AUTOLOG": "0",
            "FRAM_DEV_PROFILE": "0",
            "FRAM_FRACTAL_INFLUENCE": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    sys.path.insert(0, str(args.repo))
    from fram_eval.conversation_memory_eval import DEFAULT_LIVE_DATASET, load_eval_items
    from fram_eval.production_memory_eval import (
        merge_production_reports,
        strict_production_gate,
    )

    dataset = (args.dataset or Path(DEFAULT_LIVE_DATASET)).resolve()
    items = load_eval_items(dataset)
    if not items:
        raise ValueError("Dataset is empty")
    workers = min(args.workers, len(items))
    receipt = {
        "schema": "hearth-production-gate-supervisor-v1",
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_time": args.evaluation_time,
        "workers": workers,
        "timeout_seconds": args.timeout_seconds,
        "source_memory_root": str(args.source),
        "repository": str(args.repo),
        "dataset": str(dataset),
        "dataset_file_sha256": digest(dataset),
        "supervisor_sha256": digest(Path(__file__)),
        "item_count": len(items),
        "expected_captures": len(items) * 6,
        "profile_half_life_hours": args.half_life_hours,
        "explicit_config_sha256": digest(args.config) if args.config else None,
        "gate_thresholds_unchanged": True,
        "persistent_runtime_changed": False,
        "native_threads_per_worker": 1,
        "shards": [],
    }
    processes = []
    logs = []
    started = time.monotonic()
    try:
        for index in range(workers):
            first = len(items) * index // workers
            stop = len(items) * (index + 1) // workers
            root = args.run_root / f"shard-{index:02d}"
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(args.repo),
                    "FRAM_STORAGE_ROOT": str(args.run_root / f"bootstrap-{index:02d}"),
                    "COGMEM_STORAGE_ROOT": str(
                        args.run_root
                        / f"bootstrap-{index:02d}"
                        / "memory"
                        / "cognitive"
                    ),
                }
            )
            command = [
                sys.executable,
                "-B",
                "-m",
                "scripts.production_memory_eval",
                "--source-memory-root",
                str(args.source),
                "--scratch-root",
                str(root),
                "--dataset",
                str(dataset),
                "--fractal-enabled",
                "--item-offset",
                str(first),
                "--max-items",
                str(stop - first),
                "--evaluation-time",
                args.evaluation_time,
                "--skip-off-observation",
            ]
            if args.half_life_hours is not None:
                command.extend(["--half-life-hours", str(args.half_life_hours)])
            if args.config is not None:
                command.extend(["--config", str(args.config)])
            log_path = args.run_root / f"shard-{index:02d}.log"
            log = log_path.open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(
                command,
                cwd=args.repo,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            processes.append(process)
            receipt["shards"].append(
                {
                    "index": index,
                    "start": first,
                    "stop": stop,
                    "scratch_root": str(root),
                    "log": str(log_path),
                    "pid": process.pid,
                    "command": command,
                    "exit_code": None,
                }
            )
        last_print = -60.0
        while True:
            elapsed = time.monotonic() - started
            done = 0
            persisted = 0
            for process, shard in zip(processes, receipt["shards"]):
                shard["exit_code"] = process.poll()
                if shard["exit_code"] is not None:
                    done += 1
                progress_path = Path(shard["scratch_root"]) / "production-progress.json"
                if progress_path.exists():
                    progress = json.loads(progress_path.read_text(encoding="utf-8"))
                    shard["progress"] = {
                        key: progress.get(key)
                        for key in (
                            "status",
                            "phase",
                            "queries_attempted",
                            "queries_selected",
                            "queries_persisted",
                            "selection_seconds",
                            "active_mode",
                            "active_field",
                        )
                    }
                    persisted += progress.get("queries_persisted", 0)
            receipt.update(
                elapsed_seconds=elapsed,
                completed_shards=done,
                persisted_captures=persisted,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            atomic_json(args.run_root / "supervisor-receipt.json", receipt)
            if elapsed - last_print >= 60 or done == workers:
                print(
                    json.dumps(
                        {
                            "elapsed_seconds": round(elapsed, 1),
                            "completed_shards": done,
                            "persisted_captures": persisted,
                            "expected_captures": len(items) * 6,
                        }
                    ),
                    flush=True,
                )
                last_print = elapsed
            if any(shard["exit_code"] not in (None, 0) for shard in receipt["shards"]):
                raise RuntimeError("A production shard failed; see its preserved log")
            if done == workers:
                break
            if elapsed > args.timeout_seconds:
                raise TimeoutError(
                    "Bounded production run exceeded its declared timeout"
                )
            time.sleep(5)
        reports = [
            json.loads(
                (Path(shard["scratch_root"]) / "production-memory-eval.json").read_text(
                    encoding="utf-8"
                )
            )
            for shard in receipt["shards"]
        ]
        merged = merge_production_reports(reports, items=items, expected_shards=workers)
        merged["autoflip"] = strict_production_gate(merged, items)
        report_path = args.run_root / "production-memory-eval.json"
        atomic_json(report_path, merged)
        receipt.update(
            status="completed",
            report=str(report_path),
            report_sha256=digest(report_path),
            recommendation=merged["autoflip"]["recommend_enable"],
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        print(
            json.dumps(
                {
                    "report": str(report_path),
                    "matching": merged["matching"],
                    "autoflip": merged["autoflip"],
                }
            ),
            flush=True,
        )
        return 0
    except BaseException as exc:
        receipt.update(
            status="failed",
            error_type=type(exc).__name__,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        raise
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        for log in logs:
            log.close()
        receipt["elapsed_seconds"] = time.monotonic() - started
        atomic_json(args.run_root / "supervisor-receipt.json", receipt)


if __name__ == "__main__":
    raise SystemExit(main())
