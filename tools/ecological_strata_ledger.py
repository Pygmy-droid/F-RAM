"""Operate the local Ecological Strata append-only ledger.

This CLI records source-local protocol attestations. It cannot authenticate a
person or model and must not be used as identity proof.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.ecological_strata import EcologicalStrataLedger  # noqa: E402


def _default_root() -> Path:
    cfg = FRAMConfig.from_env()
    observability = cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    return cfg.STORAGE_ROOT / observability / "continuity" / "ecological"


def _read_terms(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("terms file must contain one JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append or verify scope-local Ecological Strata events."
    )
    parser.add_argument("--root", type=Path, default=None, help="Ledger directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "verify", help="Verify the complete digest and transition chain."
    )

    show = subparsers.add_parser("show", help="Project one relation's validated state.")
    show.add_argument("relation_id")

    append = subparsers.add_parser("append", help="Append one protocol event.")
    append.add_argument(
        "stage",
        choices=(
            "offer",
            "mirror",
            "correct",
            "consent",
            "bind",
            "return",
            "refuse",
            "revoke",
        ),
    )
    append.add_argument("--relation-id", required=True)
    append.add_argument("--actor-id", required=True)
    append.add_argument("--statement", required=True)
    append.add_argument(
        "--source-class",
        required=True,
        choices=(
            "human_statement",
            "model_output",
            "system_observation",
            "artifact",
            "code_test",
            "unknown",
        ),
    )
    append.add_argument("--source-ref", required=True)
    append.add_argument(
        "--attestation",
        default="direct",
        choices=("direct", "relayed", "inferred", "unknown"),
    )
    append.add_argument(
        "--participant",
        dest="participants",
        action="append",
        help="Participant ID; repeat for offer (or for an equality check later).",
    )
    append.add_argument("--terms-file", help="Canonical JSON terms for offer/correct.")
    append.add_argument("--expected-terms-digest")
    append.add_argument("--observed-at-utc")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root if args.root is not None else _default_root()
    ledger = EcologicalStrataLedger(root)

    if args.command == "verify":
        value = ledger.verify()
    elif args.command == "show":
        value = ledger.project(args.relation_id).to_dict()
    else:
        value = ledger.append(
            relation_id=args.relation_id,
            stage=args.stage,
            actor_id=args.actor_id,
            statement=args.statement,
            source={
                "class": args.source_class,
                "ref": args.source_ref,
                "attestation": args.attestation,
            },
            participants=args.participants,
            terms=_read_terms(args.terms_file),
            expected_terms_digest=args.expected_terms_digest,
            observed_at_utc=args.observed_at_utc,
        )
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
