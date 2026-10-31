from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import ForgetDecision, compute_decay_factor, decide_forgetting
from fram_serving.memory.retention_curve import compute_retention_score


DEFAULT_AGE_MULTIPLIERS: Sequence[float] = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0)
DEFAULT_BASE_SCORES: Sequence[float] = (0.2, 0.5, 0.8)


@dataclass
class CalibrationEntry:
    age_days: float
    base_score: float
    retention_score: float
    decay_factor: float
    forget_score: float
    decision_dry: str
    decision_enforce: str


@dataclass
class CalibrationResult:
    config: dict
    grid: List[CalibrationEntry]
    decision_counts: dict


def _apply_lifecycle_scores(age_days: float, base_score: float, config: FRAMConfig) -> tuple[float, float, float]:
    """Mirror the pipeline order: base -> retention -> decay -> forget_score."""
    age_seconds = max(0.0, age_days * 86400.0)
    retention_enabled = bool(getattr(config, "enable_retention_curve", False))
    decay_enabled = bool(getattr(config, "enable_decay", False))
    retention = compute_retention_score(age_seconds, config) if retention_enabled else 1.0
    decay = compute_decay_factor(age_seconds, config) if decay_enabled else 1.0
    forget_score = float(base_score)
    if retention_enabled:
        forget_score *= retention
    if decay_enabled:
        forget_score *= decay
    return retention, decay, forget_score


def calibration_grid(
    config: FRAMConfig,
    age_multipliers: Sequence[float] = DEFAULT_AGE_MULTIPLIERS,
    base_scores: Sequence[float] = DEFAULT_BASE_SCORES,
) -> CalibrationResult:
    half_life_days = float(getattr(config, "retention_half_life_days", 30.0))
    ages_days = [max(0.0, m * half_life_days) for m in age_multipliers]
    total_candidates = len(ages_days) * len(base_scores)
    grid: List[CalibrationEntry] = []
    decision_counts = {"dry_run": {"keep": 0, "forget_dry": 0, "forget_enforce": 0}, "enforce": {"keep": 0, "forget_dry": 0, "forget_enforce": 0}}

    for age_days in ages_days:
        for base_score in base_scores:
            retention, decay, forget_score = _apply_lifecycle_scores(age_days, base_score, config)
            decisions: dict[str, ForgetDecision] = {}
            for mode in ("dry_run", "enforce"):
                cfg_mode = config.model_copy(update={"hard_forgetting_mode": mode, "enable_hard_forgetting": True})
                decision = decide_forgetting(
                    None,
                    {"forget_score": forget_score, "retention_score": retention, "decay_factor": decay},
                    cfg_mode,
                    active_count=total_candidates,
                )
                decisions[mode] = decision
                key = "forget_enforce" if decision == ForgetDecision.FORGET_ENFORCE else ("forget_dry" if decision == ForgetDecision.FORGET_DRY else "keep")
                decision_counts[mode][key] += 1
            grid.append(
                CalibrationEntry(
                    age_days=age_days,
                    base_score=base_score,
                    retention_score=retention,
                    decay_factor=decay,
                    forget_score=forget_score,
                    decision_dry=decisions["dry_run"].value,
                    decision_enforce=decisions["enforce"].value,
                )
            )

    return CalibrationResult(config=config.model_dump(), grid=grid, decision_counts=decision_counts)


def _print_table(result: CalibrationResult) -> None:
    headers = ["age_days", "base", "retention", "decay", "forget_score", "dry", "enforce"]
    print("\t".join(headers))
    for entry in result.grid:
        print(
            f"{entry.age_days:.2f}\t{entry.base_score:.2f}\t{entry.retention_score:.4f}\t"
            f"{entry.decay_factor:.4f}\t{entry.forget_score:.4f}\t{entry.decision_dry}\t{entry.decision_enforce}"
        )
    print("\ndecision_counts:")
    print(json.dumps(result.decision_counts, indent=2, ensure_ascii=False))


def build_config(args: argparse.Namespace) -> FRAMConfig:
    base = FRAMConfig.from_env()
    updates = {}
    if args.enable_retention_curve:
        updates["enable_retention_curve"] = True
    if args.enable_decay:
        updates["enable_decay"] = True
    if args.enable_hard_forgetting:
        updates["enable_hard_forgetting"] = True
    if args.retention_half_life_days is not None:
        updates["retention_half_life_days"] = float(args.retention_half_life_days)
    if args.forgetting_half_life_days is not None:
        updates["forgetting_half_life_days"] = float(args.forgetting_half_life_days)
    if args.forgetting_threshold is not None:
        updates["forgetting_threshold"] = float(args.forgetting_threshold)
    if args.min_active_items is not None:
        updates["min_active_items"] = int(args.min_active_items)
    if args.hard_forgetting_mode:
        updates["hard_forgetting_mode"] = str(args.hard_forgetting_mode)
    if updates:
        return base.model_copy(update=updates)
    return base


def parse_floats(values: Iterable[str]) -> List[float]:
    return [float(v) for v in values]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase F calibration sweep (synthetic, read-only).")
    parser.add_argument("--enable-retention-curve", action="store_true", help="Enable retention curve during the sweep.")
    parser.add_argument("--enable-decay", action="store_true", help="Enable decay during the sweep.")
    parser.add_argument("--enable-hard-forgetting", action="store_true", help="Enable hard forgetting during the sweep.")
    parser.add_argument("--retention-half-life-days", type=float, help="Override retention_half_life_days.")
    parser.add_argument("--forgetting-half-life-days", type=float, help="Override forgetting_half_life_days.")
    parser.add_argument("--forgetting-threshold", type=float, help="Override forgetting_threshold.")
    parser.add_argument("--min-active-items", type=int, help="Override min_active_items.")
    parser.add_argument("--hard-forgetting-mode", choices=["dry_run", "enforce"], help="Mode used for the sweep decisions.")
    parser.add_argument("--age-multipliers", nargs="+", type=float, default=list(DEFAULT_AGE_MULTIPLIERS), help="Age multipliers relative to the retention half-life.")
    parser.add_argument("--base-scores", nargs="+", type=float, default=list(DEFAULT_BASE_SCORES), help="Base scores to sweep.")
    parser.add_argument("--json-out", type=str, help="Optional path to write the sweep JSON.")
    args = parser.parse_args(argv)

    config = build_config(args)
    result = calibration_grid(config, age_multipliers=args.age_multipliers, base_scores=args.base_scores)
    _print_table(result)

    if args.json_out:
        payload = {
            "config": result.config,
            "decision_counts": result.decision_counts,
            "grid": [
                {
                    "age_days": e.age_days,
                    "base_score": e.base_score,
                    "retention_score": e.retention_score,
                    "decay_factor": e.decay_factor,
                    "forget_score": e.forget_score,
                    "decision_dry": e.decision_dry,
                    "decision_enforce": e.decision_enforce,
                }
                for e in result.grid
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
