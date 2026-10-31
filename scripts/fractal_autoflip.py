from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from fram_eval.fractal_autoflip import (
    DEFAULT_CONVERSATION_EVAL,
    DEFAULT_OUT,
    DEFAULT_SHADOW_EVAL,
    recommend_from_paths,
)


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend when to enable fractal influence.")
    parser.add_argument(
        "--conversation",
        type=Path,
        default=DEFAULT_CONVERSATION_EVAL,
        help=f"Conversation eval JSON path (default: {DEFAULT_CONVERSATION_EVAL}).",
    )
    parser.add_argument(
        "--shadow",
        type=Path,
        default=DEFAULT_SHADOW_EVAL,
        help=f"Shadow eval JSON path (default: {DEFAULT_SHADOW_EVAL}).",
    )
    parser.add_argument(
        "--fields",
        default="probe,probe_low_lex",
        help="Comma-separated fields to evaluate.",
    )
    parser.add_argument(
        "--low-lex-fields",
        default="probe_low_lex",
        help="Comma-separated fields treated as low-lex.",
    )
    parser.add_argument(
        "--top1-margin",
        type=float,
        default=0.02,
        help="Required top1 lift over the best baseline (semantic/lexical).",
    )
    parser.add_argument(
        "--shadow-margin",
        type=float,
        default=-0.01,
        help="Required avg_delta lift over the best baseline.",
    )
    parser.add_argument(
        "--low-lex-top1-margin",
        type=float,
        default=0.02,
        help="Top1 margin used for low-lex fields.",
    )
    parser.add_argument(
        "--low-lex-shadow-margin",
        type=float,
        default=-0.01,
        help="Avg_delta margin used for low-lex fields.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=6,
        help="Minimum required count per field/mode.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output JSON path.",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="Print FRAM_FRACTAL_INFLUENCE env suggestion to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fields = _parse_list(args.fields)
    low_lex_fields = _parse_list(args.low_lex_fields)
    payload = recommend_from_paths(
        args.conversation,
        args.shadow,
        fields=fields,
        low_lex_fields=low_lex_fields,
        top1_margin=args.top1_margin,
        shadow_margin=args.shadow_margin,
        low_lex_top1_margin=args.low_lex_top1_margin,
        low_lex_shadow_margin=args.low_lex_shadow_margin,
        min_count=args.min_count,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    decision = "ENABLE" if payload.get("recommend_enable") else "KEEP_OFF"
    print(f"fractal_influence_recommendation={decision}")
    if args.print_env:
        env_value = "1" if payload.get("recommend_enable") else "0"
        print(f"FRAM_FRACTAL_INFLUENCE={env_value}")


if __name__ == "__main__":
    main()
