from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig
from fram_serving.memory.retention_curve import compute_retention_score
from fram_serving.memory.forgetting import compute_decay_factor


def _format_rows(headers: Iterable[str], rows: list[list[str]]) -> str:
    cols = list(headers)
    widths = [len(h) for h in cols]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    def _fmt(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
    sep = "-+-".join("-" * w for w in widths)
    out = [_fmt(cols), sep]
    out.extend(_fmt(r) for r in rows)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase E retention/forgetting summary")
    parser.add_argument("--half-life-days", type=float, default=None, help="Override retention/forgetting half-life for preview")
    args = parser.parse_args()

    cfg = FRAMConfig.from_env()
    retention_half = args.half_life_days if args.half_life_days is not None else cfg.retention_half_life_days
    forgetting_half = args.half_life_days if args.half_life_days is not None else cfg.forgetting_half_life_days

    print("Phase E Configuration")
    print("---------------------")
    print(f"enable_retention_curve: {cfg.enable_retention_curve}")
    print(f"retention_half_life_days: {cfg.retention_half_life_days}")
    print(f"enable_decay: {cfg.enable_decay}")
    print(f"forgetting_half_life_days: {cfg.forgetting_half_life_days}")
    print(f"enable_hard_forgetting: {cfg.enable_hard_forgetting}")
    print(f"hard_forgetting_mode: {cfg.hard_forgetting_mode}")
    print(f"forgetting_threshold: {cfg.forgetting_threshold}")
    print(f"min_active_items: {cfg.min_active_items}")
    print()

    # Compute scores with gates forced on for illustration.
    cfg_eval = cfg.model_copy(
        update={
            "enable_retention_curve": True,
            "enable_decay": True,
            "retention_half_life_days": retention_half,
            "forgetting_half_life_days": forgetting_half,
        }
    )

    ages_days = [0.0, retention_half / 2, retention_half, 2 * retention_half, 5 * retention_half]
    headers = ["age_days", "retention_score", "decay_factor", "forget_score"]
    rows: list[list[str]] = []
    for age in ages_days:
        age_seconds = age * 86400.0
        r = compute_retention_score(age_seconds=age_seconds, config=cfg_eval)
        d = compute_decay_factor(age_seconds=age_seconds, config=cfg_eval)
        forget_score = r * d
        rows.append(
            [
                f"{age:.2f}",
                f"{r:.4f}",
                f"{d:.4f}",
                f"{forget_score:.4f}",
            ]
        )

    print("Preview (gates forced on for shape)")
    print(_format_rows(headers, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
