from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator


def ingest_demo_corpus(
    *,
    storage_root: Path | None = None,
    data_root: Path | None = None,
    persist_subdir: str | None = None,
    include_legacy: bool = False,
) -> Path:
    """Build and persist the demo corpus assets under ``storage_root``.

    Parameters
    ----------
    storage_root:
        Root directory for persisted assets. Defaults to the configured
        ``FRAMConfig.STORAGE_ROOT``.
    data_root:
        Directory containing the source documents. Defaults to ``examples/data``.
    persist_subdir:
        Optional name for the corpus subdirectory inside the index storage.

    Returns
    -------
    Path
        The directory where the serialized corpus was written.
    """

    cfg = FRAMConfig()
    target_storage = Path(storage_root) if storage_root is not None else Path(cfg.STORAGE_ROOT)
    target_storage.mkdir(parents=True, exist_ok=True)

    data_source = Path(data_root) if data_root is not None else Path(__file__).resolve().parents[1] / "examples" / "data"
    index_folder = target_storage / cfg.STORAGE_SUBFOLDERS.get("index", "index")
    if persist_subdir is None:
        persist_path = index_folder / "demo_corpus"
    else:
        persist_path = index_folder / persist_subdir

    config_override = cfg.model_copy(update={"STORAGE_ROOT": target_storage})

    orchestrator = QueryOrchestrator(
        config=config_override,
        tracer=None,
        data_root=data_source,
        persist_path=persist_path,
        include_legacy=include_legacy,
    )
    orchestrator.ensure_corpus()
    return persist_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persist the demo F-RAM corpus to storage.")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Destination storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Source data directory (defaults to examples/data).",
    )
    parser.add_argument(
        "--persist-subdir",
        type=str,
        default=None,
        help="Optional corpus subdirectory name inside the index storage.",
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Include legacy fixtures (doc1/doc2) when building the corpus.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress status output (still prints destination on stdout).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    persist_path = ingest_demo_corpus(
        storage_root=args.storage_root,
        data_root=args.data_root,
        persist_subdir=args.persist_subdir,
        include_legacy=args.include_legacy,
    )

    if args.quiet:
        print(persist_path)
    else:
        print(f"Persisted corpus artifacts to {persist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
