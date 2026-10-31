"""Offline, source-labelled actual production cognitive-selection evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fram_eval.conversation_memory_eval import DEFAULT_LIVE_DATASET, load_eval_items
from fram_eval.production_memory_eval import evaluate_production, strict_production_gate
from fram_serving.config import FRAMConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-memory-root", required=True, type=Path)
    parser.add_argument(
        "--scratch-root", required=True, type=Path, help="new disposable directory"
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_LIVE_DATASET)
    parser.add_argument(
        "--config",
        type=Path,
        help="explicit FRAMConfig JSON; environment is not a profile",
    )
    parser.add_argument(
        "--half-life-hours",
        type=float,
        help="explicit candidate recency half-life; default remains 12h",
    )
    parser.add_argument(
        "--fractal-enabled",
        action="store_true",
        help="explicitly enable trace scoring in candidate profile",
    )
    parser.add_argument("--modes", default="semantic,lexical,fractal")
    parser.add_argument("--fields", default="probe,probe_low_lex")
    parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        help="positive bound; defaults to one-item smoke",
    )
    parser.add_argument("--shadow-k", type=int, default=3)
    parser.add_argument("--item-offset", type=int, default=0)
    parser.add_argument(
        "--evaluation-time",
        help="shared timezone-aware ISO timestamp for all paired ranking clocks",
    )
    parser.add_argument(
        "--skip-off-observation",
        action="store_true",
        help="skip OFF-mode fractal observation only after actual chunk delivery",
    )
    parser.add_argument("--shadow-max-chars", type=int, default=2000)
    args = parser.parse_args()
    values = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    unknown = set(values) - set(FRAMConfig.model_fields)
    if unknown:
        parser.error(f"unknown configuration fields: {sorted(unknown)}")
    if args.half_life_hours is not None:
        values["cognitive_memory_half_life_hours"] = args.half_life_hours
    if args.fractal_enabled:
        values["fractal_enabled"] = True
    config = FRAMConfig.model_validate(values)
    fields = args.fields.split(",")
    items = load_eval_items(args.dataset)
    report = evaluate_production(
        items,
        source_memory_root=args.source_memory_root,
        scratch_root=args.scratch_root,
        config=config,
        modes=args.modes.split(","),
        fields=fields,
        max_items=args.max_items,
        item_offset=args.item_offset,
        evaluation_time=args.evaluation_time,
        skip_off_observation=args.skip_off_observation,
        shadow_k=args.shadow_k,
        shadow_max_chars=args.shadow_max_chars,
    )
    gate = strict_production_gate(report, items)
    report["autoflip"] = gate
    out = args.scratch_root / "production-memory-eval.json"
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "report": str(out),
                "matching": report["matching"],
                "trace_cache": report["trace_cache"],
                "recommend_enable": gate["recommend_enable"],
                "reasons": gate["reasons"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
