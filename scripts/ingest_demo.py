"""Persist the demo corpus under storage/ for rapid startup.

This legacy helper stays alongside the newer `fram_serving.ingest` CLI so
existing docs still work. It now skips the legacy demo fixtures (`doc1/doc2`)
unless `--include-legacy` is provided.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from fram_core.calibrate import main as calibrate_main
from fram_core.pipeline import export_claim_log, load_demo_corpus, save_corpus_cache
from fram_serving.config import FRAMConfig


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist demo corpus assets for FRAM")
    parser.add_argument(
        "--embedding-backend",
        choices=["vocab", "hashing", "tfidf"],
        default=None,
        help="Override FRAM_EMBEDDING_BACKEND for this run",
    )
    parser.add_argument(
        "--skip-calibration",
        action="store_true",
        help="Skip calibration even if a log exists",
    )
    parser.add_argument(
        "--calibration-log",
        type=Path,
        default=None,
        help="Optional override for calibration log path",
    )
    parser.add_argument(
        "--calibration-out",
        type=Path,
        default=None,
        help="Optional override for calibration payload destination",
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Include legacy fixtures (doc1/doc2) when building the corpus",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    cfg = FRAMConfig.from_env()
    if args.embedding_backend is not None:
        cfg = cfg.model_copy(update={"embedding_backend": args.embedding_backend})

    data_root = PROJECT_ROOT / "examples" / "data"
    index_dir = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("index", "index") / "demo_corpus"
    claims_dir = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("claims", "claims")

    cache = load_demo_corpus(data_root, cfg, include_legacy=args.include_legacy)
    save_corpus_cache(cache, index_dir)
    claim_log_path = export_claim_log(cache, claims_dir, dataset_name="demo_corpus")

    print(f"Persisted demo corpus to {index_dir}")
    print(f"Wrote claim log to {claim_log_path}")

    log_path = args.calibration_log or (cfg.STORAGE_ROOT / "observability" / "calibration.jsonl")
    out_path = args.calibration_out or (index_dir / "calibration.json")
    if not args.skip_calibration and log_path.exists():
        print(f"Refreshing calibration payload from {log_path}")
        calibrate_main(["--log", str(log_path), "--out", str(out_path)])
        print(f"Updated calibration payload at {out_path}")
    else:
        print(f"Skipping calibration refresh (log not found at {log_path})")


if __name__ == "__main__":
    main()
