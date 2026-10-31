from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from fram_serving.config import FRAMConfig
from fram_serving.fractal_memory import build_query_path, downsample_path, soft_dtw_distance
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_OUT = Path("storage/observability/fractal_trace_alignment_probe.json")


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _normalize(vec: np.ndarray) -> Optional[np.ndarray]:
    if vec.size == 0:
        return None
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return None
    return vec / norm


def _seed_value(episode_id: str, timestamp_ms: int, vector: np.ndarray) -> int:
    buffer = np.asarray(vector, dtype=np.float32).tobytes()
    digest = hashlib.blake2s(digest_size=16)
    digest.update(episode_id.encode("utf-8"))
    digest.update(str(timestamp_ms).encode("utf-8"))
    digest.update(buffer)
    return int.from_bytes(digest.digest()[:8], "big")


def _cosine(a: np.ndarray | None, b: np.ndarray | None) -> Optional[float]:
    if a is None or b is None:
        return None
    if a.size == 0 or b.size == 0:
        return None
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0.0:
        return None
    return float(np.dot(a, b) / denom)


def _load_episode_times(store: CognitiveMemoryStore) -> Dict[str, int]:
    path = store.root / store.FILE_EPISODES
    if not path.exists():
        return {}
    times: Dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "episode":
                continue
            episode_id = str(record.get("id") or "")
            if not episode_id:
                continue
            stamp = _parse_iso(record.get("time"))
            timestamp_ms = int(stamp.timestamp() * 1000) if stamp else 0
            times[episode_id] = timestamp_ms
    return times


def _load_raw_vectors(path: Path) -> Dict[str, np.ndarray]:
    if not path.exists():
        return {}
    vectors: Dict[str, np.ndarray] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_id = payload.get("id")
            raw_vec = payload.get("vector")
            if not item_id or raw_vec is None:
                continue
            arr = np.asarray(raw_vec, dtype=float).ravel()
            if arr.size == 0:
                continue
            vectors[str(item_id)] = arr
    return vectors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare trace alignment for raw stored embeddings vs normalized vectors."
        )
    )
    parser.add_argument(
        "--live-store-root",
        type=Path,
        default=Path("storage/memory/cognitive"),
        help="Cognitive memory root for live evals.",
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=25,
        help="Max episodes to evaluate (0 for all).",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=11,
        help="Seed for sampling episodes.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-gamma",
        type=float,
        default=None,
        help="Override soft-DTW gamma for trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-band",
        type=float,
        default=None,
        help="Override soft-DTW band for trace scoring.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = FRAMConfig.from_env()
    store = CognitiveMemoryStore(args.live_store_root, config=cfg)
    trace_store = store.fractal_trace_store()
    if trace_store is None:
        raise SystemExit("Fractal trace store unavailable; check config.")
    vectors = _load_raw_vectors(store.vector_path(kind="episode"))
    times = _load_episode_times(store)
    trace_ids = set(trace_store.available_ids())
    candidate_ids = sorted(set(vectors.keys()) & trace_ids & set(times.keys()))
    if not candidate_ids:
        raise SystemExit("No episodes with vectors, traces, and timestamps.")

    max_episodes = int(args.max_episodes)
    if max_episodes <= 0 or max_episodes >= len(candidate_ids):
        eval_ids = list(candidate_ids)
    else:
        rng = random.Random(int(args.sample_seed))
        eval_ids = rng.sample(candidate_ids, max_episodes)

    gamma = float(args.fractal_soft_dtw_gamma) if args.fractal_soft_dtw_gamma is not None else 0.1
    band = float(args.fractal_soft_dtw_band) if args.fractal_soft_dtw_band is not None else 0.15

    summary: Dict[str, Any] = {
        "total": 0,
        "seed_match_raw": 0,
        "seed_match_norm": 0,
        "cos_raw_better": 0,
        "dtw_raw_better": 0,
        "cos_raw_mean": None,
        "cos_norm_mean": None,
        "dtw_raw_mean": None,
        "dtw_norm_mean": None,
        "q6_cos_mean": None,
    }
    cos_raw_sum = 0.0
    cos_norm_sum = 0.0
    dtw_raw_sum = 0.0
    dtw_norm_sum = 0.0
    q6_cos_sum = 0.0

    try:
        downsample_target = int(getattr(cfg, "fractal_downsample_target", 256))
    except Exception:
        downsample_target = 256
    if downsample_target <= 0:
        downsample_target = 256

    items: List[Dict[str, Any]] = []
    for episode_id in eval_ids:
        raw_vec = vectors.get(str(episode_id))
        timestamp_ms = times.get(str(episode_id))
        if raw_vec is None or timestamp_ms is None:
            continue
        norm_vec = _normalize(raw_vec)
        if norm_vec is None:
            continue
        bundle = trace_store.load_trace(str(episode_id))
        if bundle is None:
            if not store.ensure_fractal_trace(str(episode_id)):
                continue
            bundle = trace_store.load_trace(str(episode_id))
        if bundle is None:
            continue
        trace_line, _ = bundle
        provenance = trace_line.provenance or {}
        proj_seed = provenance.get("projection_seed")
        if proj_seed is None:
            continue
        try:
            proj_seed = int(proj_seed)
        except (TypeError, ValueError):
            continue

        if raw_vec.size != trace_store.generator.embedding_dim:
            continue

        coords_full = trace_store.generator.retrace(trace_line)
        coords, _ = downsample_path(coords_full, target=downsample_target)
        if coords.size == 0:
            continue
        coords = np.asarray(coords, dtype=float)
        centroid = coords.mean(axis=0)
        composite = (centroid + coords[0] + coords[-1]) / 3.0

        q6_raw = trace_store.generator.project(raw_vec, projection_seed=proj_seed)
        q6_norm = trace_store.generator.project(norm_vec, projection_seed=proj_seed)

        cos_raw = _cosine(q6_raw, composite)
        cos_norm = _cosine(q6_norm, composite)
        q6_cos = _cosine(q6_raw, q6_norm)

        raw_path = build_query_path(q6_raw, steps=coords.shape[0])
        raw_path, _ = downsample_path(raw_path, target=coords.shape[0])
        norm_path = build_query_path(q6_norm, steps=coords.shape[0])
        norm_path, _ = downsample_path(norm_path, target=coords.shape[0])
        try:
            dtw_raw = float(soft_dtw_distance(raw_path, coords, gamma=gamma, band=band))
            dtw_norm = float(soft_dtw_distance(norm_path, coords, gamma=gamma, band=band))
        except Exception:
            continue

        seed_int_raw = _seed_value(str(episode_id), int(timestamp_ms), raw_vec)
        seed_int_norm = _seed_value(str(episode_id), int(timestamp_ms), norm_vec)
        seed_hash_raw = f"{seed_int_raw:016x}"
        seed_hash_norm = f"{seed_int_norm:016x}"
        trace_seed_int = provenance.get("seed_int")
        trace_seed_hash = provenance.get("seed_hash")
        seed_match_raw = str(trace_seed_hash) == seed_hash_raw or str(trace_seed_int) == str(seed_int_raw)
        seed_match_norm = str(trace_seed_hash) == seed_hash_norm or str(trace_seed_int) == str(seed_int_norm)

        summary["total"] += 1
        if seed_match_raw:
            summary["seed_match_raw"] += 1
        if seed_match_norm:
            summary["seed_match_norm"] += 1
        if cos_raw is not None and cos_norm is not None:
            if cos_raw > cos_norm:
                summary["cos_raw_better"] += 1
            cos_raw_sum += cos_raw
            cos_norm_sum += cos_norm
        if dtw_raw < dtw_norm:
            summary["dtw_raw_better"] += 1
        dtw_raw_sum += dtw_raw
        dtw_norm_sum += dtw_norm
        if q6_cos is not None:
            q6_cos_sum += q6_cos

        items.append(
            {
                "episode_id": str(episode_id),
                "projection_seed": proj_seed,
                "seed_match_raw": seed_match_raw,
                "seed_match_norm": seed_match_norm,
                "cosine_raw": cos_raw,
                "cosine_norm": cos_norm,
                "cosine_delta": (cos_raw - cos_norm) if (cos_raw is not None and cos_norm is not None) else None,
                "q6_cosine": q6_cos,
                "soft_dtw_raw": dtw_raw,
                "soft_dtw_norm": dtw_norm,
                "soft_dtw_delta": dtw_raw - dtw_norm,
            }
        )

    total = max(1, summary["total"])
    summary["seed_match_raw"] = summary["seed_match_raw"] / total
    summary["seed_match_norm"] = summary["seed_match_norm"] / total
    summary["cos_raw_better"] = summary["cos_raw_better"] / total
    summary["dtw_raw_better"] = summary["dtw_raw_better"] / total
    summary["cos_raw_mean"] = cos_raw_sum / total if summary["total"] else None
    summary["cos_norm_mean"] = cos_norm_sum / total if summary["total"] else None
    summary["dtw_raw_mean"] = dtw_raw_sum / total if summary["total"] else None
    summary["dtw_norm_mean"] = dtw_norm_sum / total if summary["total"] else None
    summary["q6_cos_mean"] = q6_cos_sum / total if summary["total"] else None

    payload: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "store_root": str(args.live_store_root),
        "max_episodes": max_episodes,
        "sample_seed": int(args.sample_seed),
        "gamma": gamma,
        "band": band,
        "downsample_target": downsample_target,
        "summary": summary,
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
