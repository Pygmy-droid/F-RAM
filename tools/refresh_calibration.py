from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig


@dataclass(frozen=True)
class PromptJob:
    task: str
    queries_path: Path
    domain: str | None = None


@dataclass(frozen=True)
class SliceJob:
    label: str
    log_path: Path
    payload_path: Path


DEFAULT_PROMPT_JOBS = (
    PromptJob("qa", Path("scripts/calibration_prompts/definitional_queries.txt")),
    PromptJob("definitional", Path("scripts/calibration_prompts/definitional_queries.txt")),
    PromptJob("definitional", Path("scripts/calibration_prompts/definitional_soft_queries.txt")),
    PromptJob("qa", Path("scripts/calibration_prompts/definitional_low_conf_queries.txt")),
    PromptJob("definitional", Path("scripts/calibration_prompts/definitional_low_conf_queries.txt")),
    PromptJob("qa", Path("scripts/calibration_prompts/qa_moderate_queries.txt")),
)

OPTIONAL_PROMPTS = {
    "layout": Path("scripts/calibration_prompts/layout_anchor_queries.txt"),
    "diary": Path("scripts/calibration_prompts/diary_queries.txt"),
}


def _run_step(cmd: list[str], *, dry_run: bool) -> None:
    display = " ".join(cmd)
    print(f"[refresh-calibration] {display}")
    if dry_run:
        return
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def _default_log_path(cfg: FRAMConfig, storage_root: Path) -> Path:
    obs_dir = cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    return storage_root / obs_dir / "calibration.jsonl"


def _iter_records(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _filter_records(records: Iterable[dict], *, task: str | None, domain: str | None) -> list[dict]:
    task_value = task.strip().lower() if task else ""
    domain_value = domain.strip().lower() if domain else ""
    filtered: list[dict] = []
    for record in records:
        if task_value and str(record.get("task") or "").lower() != task_value:
            continue
        if domain_value and str(record.get("domain") or "").lower() != domain_value:
            continue
        filtered.append(record)
    return filtered


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh calibration artifacts by running harvest -> backfill -> slice -> fit -> lint -> status."
        )
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    parser.add_argument(
        "--tasks",
        action="append",
        default=None,
        help="Task slices to fit (repeatable). Default: qa, definitional.",
    )
    parser.add_argument(
        "--domains",
        action="append",
        default=None,
        help="Domain slices to fit (repeatable). Default: none.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Minimum records required to fit a slice (default: %(default)s).",
    )
    parser.add_argument(
        "--include-layout",
        action="store_true",
        help="Include layout-anchor prompts in harvest.",
    )
    parser.add_argument(
        "--include-diary",
        action="store_true",
        help="Include diary prompts in harvest.",
    )
    parser.add_argument(
        "--reads",
        type=int,
        default=None,
        help="Override harvest query budget reads.",
    )
    parser.add_argument(
        "--skip-harvest",
        action="store_true",
        help="Skip calibration harvest (use existing log).",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Skip calibration backfill.",
    )
    parser.add_argument(
        "--skip-slice",
        action="store_true",
        help="Skip writing filtered slice logs.",
    )
    parser.add_argument(
        "--skip-fit",
        action="store_true",
        help="Skip calibration fitting.",
    )
    parser.add_argument(
        "--skip-lint",
        action="store_true",
        help="Skip calibration lint.",
    )
    parser.add_argument(
        "--skip-status",
        action="store_true",
        help="Skip calibration status summary.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Write a timestamped backup of calibration.jsonl before backfill.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without executing them.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _build_prompt_jobs(args: argparse.Namespace) -> list[PromptJob]:
    jobs = list(DEFAULT_PROMPT_JOBS)
    if args.include_layout:
        jobs.append(PromptJob("qa", OPTIONAL_PROMPTS["layout"]))
    if args.include_diary:
        jobs.append(PromptJob("qa", OPTIONAL_PROMPTS["diary"]))
    return jobs


def _harvest_jobs(jobs: Sequence[PromptJob], *, storage_root: Path, reads: int | None, dry_run: bool) -> None:
    python = sys.executable
    for job in jobs:
        cmd = [
            python,
            str(REPO_ROOT / "scripts" / "harvest_calibration.py"),
            "--queries",
            str(job.queries_path),
            "--task",
            job.task,
            "--domain",
            job.domain or "general",
            "--quiet",
        ]
        if reads is not None:
            cmd.extend(["--reads", str(reads)])
        if storage_root is not None:
            cmd.extend(["--storage-root", str(storage_root)])
        _run_step(cmd, dry_run=dry_run)


def _backfill(storage_root: Path, *, backup: bool, dry_run: bool) -> None:
    python = sys.executable
    cmd = [
        python,
        str(REPO_ROOT / "tools" / "calibration_backfill.py"),
        "--default-domain",
        "general",
        "--default-task",
        "qa",
        "--infer-domain",
        "--infer-task",
    ]
    if storage_root is not None:
        cmd.extend(["--storage-root", str(storage_root)])
    if backup:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = storage_root / "observability" / f"calibration_backup_{timestamp}.jsonl"
        cmd.extend(["--backup", str(backup_path)])
    _run_step(cmd, dry_run=dry_run)


def _slice_logs(
    *,
    storage_root: Path,
    tasks: Sequence[str],
    domains: Sequence[str],
    min_count: int,
    dry_run: bool,
) -> list[SliceJob]:
    cfg = FRAMConfig.from_env()
    obs_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    log_path = obs_dir / "calibration.jsonl"
    slices: list[SliceJob] = []
    if dry_run:
        for task in tasks:
            slices.append(
                SliceJob(
                    label=f"task:{task}",
                    log_path=obs_dir / f"calibration_task_{task}.jsonl",
                    payload_path=storage_root / "index" / "demo_corpus" / f"calibration_task_{task}.json",
                )
            )
        for domain in domains:
            slices.append(
                SliceJob(
                    label=f"domain:{domain}",
                    log_path=obs_dir / f"calibration_{domain}.jsonl",
                    payload_path=storage_root / "index" / "demo_corpus" / f"calibration_{domain}.json",
                )
            )
        for slice_job in slices:
            print(f"[refresh-calibration] slice {slice_job.label} -> {slice_job.log_path}")
        return slices

    records = list(_iter_records(log_path))
    if not records:
        print(f"[refresh-calibration] calibration log missing or empty: {log_path}")
        return []

    for task in tasks:
        filtered = _filter_records(records, task=task, domain=None)
        if len(filtered) < min_count:
            print(f"[refresh-calibration] skip slice task:{task} ({len(filtered)} records)")
            continue
        slice_path = obs_dir / f"calibration_task_{task}.jsonl"
        _write_jsonl(slice_path, filtered)
        slices.append(
            SliceJob(
                label=f"task:{task}",
                log_path=slice_path,
                payload_path=storage_root / "index" / "demo_corpus" / f"calibration_task_{task}.json",
            )
        )

    for domain in domains:
        filtered = _filter_records(records, task=None, domain=domain)
        if len(filtered) < min_count:
            print(f"[refresh-calibration] skip slice domain:{domain} ({len(filtered)} records)")
            continue
        slice_path = obs_dir / f"calibration_{domain}.jsonl"
        _write_jsonl(slice_path, filtered)
        slices.append(
            SliceJob(
                label=f"domain:{domain}",
                log_path=slice_path,
                payload_path=storage_root / "index" / "demo_corpus" / f"calibration_{domain}.json",
            )
        )

    return slices


def _fit_calibration(log_path: Path, payload_path: Path, *, dry_run: bool) -> None:
    python = sys.executable
    cmd = [
        python,
        str(REPO_ROOT / "scripts" / "calibrate_confidence.py"),
        "--log",
        str(log_path),
        "--out",
        str(payload_path),
    ]
    _run_step(cmd, dry_run=dry_run)


def _lint(storage_root: Path, *, dry_run: bool) -> None:
    python = sys.executable
    cmd = [
        python,
        str(REPO_ROOT / "tools" / "calibration_lint.py"),
        "--storage-root",
        str(storage_root),
    ]
    _run_step(cmd, dry_run=dry_run)


def _status(storage_root: Path, *, dry_run: bool) -> None:
    python = sys.executable
    cmd = [
        python,
        str(REPO_ROOT / "tools" / "calibration_status.py"),
        "--storage-root",
        str(storage_root),
        "--corpus",
        "demo_corpus",
    ]
    _run_step(cmd, dry_run=dry_run)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = FRAMConfig.from_env()
    storage_root = Path(args.storage_root) if args.storage_root is not None else Path(cfg.STORAGE_ROOT)

    tasks = [t.strip().lower() for t in (args.tasks or []) if t.strip()] or ["qa", "definitional"]
    domains = [d.strip().lower() for d in (args.domains or []) if d.strip()]

    if not args.skip_harvest:
        _harvest_jobs(
            _build_prompt_jobs(args),
            storage_root=storage_root,
            reads=args.reads,
            dry_run=args.dry_run,
        )

    if not args.skip_backfill:
        _backfill(storage_root, backup=args.backup, dry_run=args.dry_run)

    slices: list[SliceJob] = []
    if not args.skip_slice:
        slices = _slice_logs(
            storage_root=storage_root,
            tasks=tasks,
            domains=domains,
            min_count=max(1, int(args.min_count)),
            dry_run=args.dry_run,
        )

    if not args.skip_fit:
        log_path = _default_log_path(cfg, storage_root)
        payload_path = storage_root / "index" / "demo_corpus" / "calibration.json"
        _fit_calibration(log_path, payload_path, dry_run=args.dry_run)
        for slice_job in slices:
            _fit_calibration(slice_job.log_path, slice_job.payload_path, dry_run=args.dry_run)

    if not args.skip_lint:
        _lint(storage_root, dry_run=args.dry_run)

    if not args.skip_status:
        _status(storage_root, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
