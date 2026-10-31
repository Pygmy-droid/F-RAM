#!/usr/bin/env python
"""Summarize FRAM calibration payloads stored on disk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Mapping

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig
from fram_core.pipeline import CalibrationPayload, _deserialize_calibration


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show the taus/temperature/logistic coefficients for stored calibration payloads.",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    parser.add_argument(
        "--corpus",
        default="demo_corpus",
        help="Corpus directory under the index folder to inspect (default: demo_corpus).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a text summary.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _load_payload(path: Path, config: FRAMConfig) -> CalibrationPayload | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid calibration payload JSON: {path} ({exc})") from exc
    if not isinstance(data, Mapping):
        raise SystemExit(f"Calibration payload must be an object: {path}")
    return _deserialize_calibration(data, config)


def _payload_summary(payload: CalibrationPayload | None) -> dict[str, object] | None:
    if payload is None:
        return None
    return {
        "tau1": float(payload.tau1),
        "tau2": float(payload.tau2),
        "temperature": float(payload.temperature),
        "logistic_coefs": dict(payload.logistic_coefs),
    }


def _collect_payloads(cfg: FRAMConfig, storage_root: Path, corpus: str) -> dict[str, object]:
    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index")
    corpus_dir = index_dir / corpus
    if not corpus_dir.exists():
        raise SystemExit(f"Corpus not found: {corpus_dir}")

    global_payload = _load_payload(corpus_dir / "calibration.json", cfg)

    domain_payloads: dict[str, CalibrationPayload | None] = {}
    task_payloads: dict[str, CalibrationPayload | None] = {}

    domain_candidates = set()
    default_domain = cfg.default_domain if isinstance(cfg.default_domain, str) else None
    if default_domain:
        domain_candidates.add(default_domain.strip().lower())
    for name in getattr(cfg, "domain_overrides", {}) or {}:
        text = str(name).strip().lower()
        if text:
            domain_candidates.add(text)

    task_candidates = set()
    default_task = cfg.default_task if isinstance(cfg.default_task, str) else None
    if default_task:
        task_candidates.add(default_task.strip().lower())
    for name in getattr(cfg, "task_overrides", {}) or {}:
        text = str(name).strip().lower()
        if text:
            task_candidates.add(text)

    for name in sorted(domain_candidates):
        domain_payloads[name] = None
    for name in sorted(task_candidates):
        task_payloads[name] = None

    for path in sorted(corpus_dir.glob("calibration*.json")):
        if path.name == "calibration.json":
            continue
        name = path.stem
        if name.startswith("calibration_task_"):
            key = name[len("calibration_task_"):].strip().lower()
            if key:
                task_payloads[key] = _load_payload(path, cfg)
        elif name.startswith("calibration_"):
            key = name[len("calibration_"):].strip().lower()
            if key:
                domain_payloads[key] = _load_payload(path, cfg)

    return {
        "default_domain": cfg.default_domain,
        "default_task": cfg.default_task,
        "global": _payload_summary(global_payload),
        "domains": {
            name: _payload_summary(payload) for name, payload in sorted(domain_payloads.items())
        },
        "tasks": {
            name: _payload_summary(payload) for name, payload in sorted(task_payloads.items())
        },
    }


def _print_summary(summary: Mapping[str, object]) -> None:
    print(f"Defaults: domain={summary['default_domain']} task={summary['default_task']}")

    global_payload = summary.get("global")
    if global_payload:
        payload = global_payload
        print(
            "Global: tau1={tau1:.4f} tau2={tau2:.4f} temp={temperature:.3f} coefs={coefs}".format(
                tau1=payload["tau1"],
                tau2=payload["tau2"],
                temperature=payload["temperature"],
                coefs=",".join(sorted((payload.get("logistic_coefs") or {}).keys())),
            )
        )
    else:
        print("Global: <missing>")

    domains = summary.get("domains", {})
    if domains:
        print("Domains:")
        for name, payload in sorted(domains.items()):
            if payload is None:
                print(f"  - {name}: <missing>")
                continue
            print(
                "  - {name}: tau1={tau1:.4f} tau2={tau2:.4f} temp={temperature:.3f}".format(
                    name=name,
                    tau1=payload["tau1"],
                    tau2=payload["tau2"],
                    temperature=payload["temperature"],
                )
            )
    else:
        print("Domains: <none>")

    tasks = summary.get("tasks", {})
    if tasks:
        print("Tasks:")
        for name, payload in sorted(tasks.items()):
            if payload is None:
                print(f"  - {name}: <missing>")
                continue
            print(
                "  - {name}: tau1={tau1:.4f} tau2={tau2:.4f} temp={temperature:.3f}".format(
                    name=name,
                    tau1=payload["tau1"],
                    tau2=payload["tau2"],
                    temperature=payload["temperature"],
                )
            )
    else:
        print("Tasks: <none>")


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = FRAMConfig.from_env()
    storage_root = args.storage_root or Path(cfg.STORAGE_ROOT)

    summary = _collect_payloads(cfg, storage_root, args.corpus)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
