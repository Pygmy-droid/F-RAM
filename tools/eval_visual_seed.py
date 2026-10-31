#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_eval.visual_seed import (  # noqa: E402
    TransformersClipEncoder,
    evaluate_visual_seeds,
    load_visual_seed_manifest,
    render_candidate_review,
    require_immutable_model_revision,
)
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer  # noqa: E402
from fram_serving.config import FRAMConfig  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only, human-review visual-seed candidate packet. "
            "F-RAM text candidates stay primary; CLIP candidates only append."
        )
    )
    parser.add_argument("--db", required=True, type=Path, help="checkpointed lived DB")
    parser.add_argument("--manifest", required=True, type=Path, help="visual seed JSON")
    parser.add_argument(
        "--output", required=True, type=Path, help="candidate report JSON"
    )
    parser.add_argument(
        "--review-output",
        type=Path,
        default=None,
        help="optional Markdown human-label sheet",
    )
    parser.add_argument(
        "--sticky-db", type=Path, default=None, help="optional plum.sqlite"
    )
    parser.add_argument("--model-id", default="openai/clip-vit-base-patch32")
    parser.add_argument(
        "--model-revision",
        default=None,
        help="exact model commit; resolved from the model registry when omitted",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--supplemental-limit", type=int, default=3)
    parser.add_argument("--sticky-candidate-limit", type=int, default=12)
    parser.add_argument("--embedding-dim", type=int, default=1024)
    parser.add_argument(
        "--include-sensitive-details",
        action="store_true",
        help="include absolute paths and query/answer previews in local-only reports",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing report files after all source-alias checks pass",
    )
    return parser


def _resolve_revision(model_id: str, revision: str | None) -> tuple[str | None, str]:
    requested = str(revision).strip() if revision else None
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:  # pragma: no cover - environment specific
        raise RuntimeError(
            "huggingface_hub is required to pin the model revision"
        ) from exc
    info = HfApi().model_info(model_id, revision=requested)
    if not info.sha:
        raise RuntimeError(f"could not resolve an exact revision for {model_id}")
    return requested, require_immutable_model_revision(str(info.sha))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path_key(path: Path) -> str:
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _protected_source_paths(paths: Sequence[Path]) -> list[Path]:
    protected: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).resolve(strict=False)
        protected.append(path)
        if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            protected.extend((Path(str(path) + "-wal"), Path(str(path) + "-shm")))
    return protected


def _validate_output_paths(
    *,
    inputs: Sequence[Path],
    output: Path,
    review_output: Path,
    force: bool,
) -> tuple[Path, Path]:
    resolved_output = Path(output).resolve(strict=False)
    resolved_review = Path(review_output).resolve(strict=False)
    if _path_key(resolved_output) == _path_key(resolved_review):
        raise ValueError("output and review-output must be different files")
    source_keys = {_path_key(path) for path in _protected_source_paths(inputs)}
    for candidate in (resolved_output, resolved_review):
        if _path_key(candidate) in source_keys:
            raise ValueError(f"report output aliases a protected source: {candidate}")
        if candidate.exists() and candidate.is_dir():
            raise IsADirectoryError(candidate)
        if candidate.exists() and not force:
            raise FileExistsError(
                f"report output already exists (use --force to replace): {candidate}"
            )
    return resolved_output, resolved_review


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    requested_revision, revision = _resolve_revision(args.model_id, args.model_revision)
    seeds = load_visual_seed_manifest(args.manifest)
    manifest_path = args.manifest.resolve()
    manifest_hash_before = _sha256_file(manifest_path)
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    review_output = args.review_output or args.output.with_suffix(".review.md")
    protected_inputs = [args.db, manifest_path, *(seed.image_path for seed in seeds)]
    if args.sticky_db is not None:
        protected_inputs.append(args.sticky_db)
    output, review_output = _validate_output_paths(
        inputs=protected_inputs,
        output=args.output,
        review_output=review_output,
        force=bool(args.force),
    )
    config = FRAMConfig().model_copy(
        update={
            "embedding_dim": int(args.embedding_dim),
            "cognitive_memory_embedding_backend": "hashing",
        }
    )
    vectorizer = build_cognitive_vectorizer(config)
    if vectorizer is None:
        raise RuntimeError("hashing vectorizer is unavailable")
    encoder = TransformersClipEncoder(
        args.model_id,
        revision=revision,
        requested_revision=requested_revision,
        device=args.device,
        batch_size=max(1, int(args.batch_size)),
    )
    report = evaluate_visual_seeds(
        args.db,
        seeds,
        vectorizer,
        encoder,
        sticky_database=args.sticky_db,
        k=max(1, int(args.k)),
        supplemental_limit=max(0, int(args.supplemental_limit)),
        sticky_candidate_limit=max(0, int(args.sticky_candidate_limit)),
        include_sensitive_details=bool(args.include_sensitive_details),
    )
    manifest_hash_after = _sha256_file(manifest_path)
    if manifest_hash_after != manifest_hash_before:
        raise RuntimeError("visual seed manifest changed during evaluation")
    report["source"].update(
        {
            "visual_manifest": (
                str(manifest_path) if args.include_sensitive_details else None
            ),
            "visual_manifest_path_in_report": bool(args.include_sensitive_details),
            "visual_manifest_sha256": manifest_hash_before,
            "visual_manifest_source_unchanged": True,
            "visual_evidence_manifest_sha256": manifest_payload[
                "visual_evidence_manifest_sha256"
            ],
        }
    )
    report_text = (
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    review_text = render_candidate_review(report)
    if len(report_text.encode("utf-8")) > 64 * 1024 * 1024:
        raise ValueError("candidate report exceeds the 64 MiB output limit")
    if len(review_text.encode("utf-8")) > 16 * 1024 * 1024:
        raise ValueError("candidate review exceeds the 16 MiB output limit")
    _atomic_write_text(output, report_text)
    _atomic_write_text(review_output, review_text)
    print(
        json.dumps(
            {
                "output": str(output),
                "review_output": str(review_output),
                "status": report["status"],
                "model_revision": revision,
                "visual_seed_count": len(report["visual_seeds"]),
                "sticky_note_count": (
                    report["source"]["sticky_notes"]["active_note_count"]
                    if report["source"]["sticky_notes"]
                    else 0
                ),
                "unique_event_content_count": report["source"][
                    "unique_event_content_count"
                ],
                "global_enable_recommendation": report["contract"][
                    "global_enable_recommendation"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
