from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.config import FRAMConfig


ROLE_WEIGHTS = {
    "user": 1.0,
    "assistant": 0.8,
    "system": 0.6,
    "tool": 0.6,
    "memory": 0.5,
}
DEFAULT_SEED = 1337


def _load_capsule(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Capsule not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in capsule: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Capsule payload is not a JSON object: {path}")
    return payload


def _extract_trajectory(payload: Dict[str, Any]) -> Tuple[np.ndarray, List[str]]:
    trajectory = payload.get("trajectory") or []
    raw = payload.get("raw_transcript") or []
    if not trajectory:
        raise SystemExit("Capsule has no trajectory embeddings.")
    embeddings: List[np.ndarray] = []
    for entry in trajectory:
        emb = entry.get("embedding")
        if emb is None:
            raise SystemExit("Trajectory entry missing embedding.")
        vec = np.asarray(emb, dtype=float).ravel()
        if vec.size == 0:
            raise SystemExit("Trajectory embedding is empty.")
        embeddings.append(vec)
    roles = [turn.get("role") for turn in raw]
    if len(roles) < len(embeddings):
        roles += ["memory"] * (len(embeddings) - len(roles))
    roles = [str(role or "memory").lower() for role in roles[: len(embeddings)]]
    return np.vstack(embeddings), roles


def _default_query(payload: Dict[str, Any]) -> str:
    raw = payload.get("raw_transcript") or []
    for turn in reversed(raw):
        if str(turn.get("role") or "").lower() == "user":
            text = str(turn.get("text") or "").strip()
            if text:
                return text
    if raw:
        return str(raw[-1].get("text") or "").strip()
    return ""


def _build_vectorizer(cfg: FRAMConfig, backend: str) -> Any | None:
    if backend == "hashing":
        return _pipeline_make_hashing_vectorizer(cfg)
    return build_cognitive_vectorizer(cfg)


def _embed_query(text: str, *, cfg: FRAMConfig, backend: str, expected_dim: int) -> np.ndarray:
    vectorizer = _build_vectorizer(cfg, backend)
    if vectorizer is None:
        raise SystemExit(f"Embedding backend '{backend}' unavailable.")
    matrix = vectorizer.transform([text])
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()
    else:
        arr = np.asarray(matrix, dtype=float)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    vec = arr.astype(float, copy=False).ravel()
    if vec.size != expected_dim:
        raise SystemExit(
            f"Query embedding dim {vec.size} != capsule dim {expected_dim}."
        )
    return vec


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return np.zeros_like(vec)
    return vec / norm


def _position_weights(n: int) -> np.ndarray:
    if n <= 1:
        return np.ones((max(n, 1),), dtype=float)
    idx = np.arange(n, dtype=float)
    return 0.5 + 0.5 * (idx / float(n - 1))


def _role_weights(roles: List[str]) -> np.ndarray:
    return np.array([ROLE_WEIGHTS.get(role, ROLE_WEIGHTS["memory"]) for role in roles], dtype=float)


def _score_alignment(
    query: np.ndarray,
    trajectory: np.ndarray,
    roles: List[str],
    *,
    top_k: int = 3,
) -> Dict[str, float]:
    q = _normalize(query)
    emb = np.asarray(trajectory, dtype=float)
    if emb.ndim != 2:
        raise SystemExit("Trajectory embeddings must be 2-D.")
    normed = np.vstack([_normalize(row) for row in emb])
    weights = _position_weights(normed.shape[0]) * _role_weights(roles)
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        weights = np.ones_like(weights)
        weight_sum = float(weights.sum())
    weights = weights / weight_sum
    signature = np.sum(normed * weights[:, None], axis=0)
    path_score = float(np.dot(q, _normalize(signature)))
    turn_scores = (normed @ q) * _role_weights(roles)
    k = max(1, min(int(top_k), turn_scores.size))
    bag_score = float(np.mean(np.sort(turn_scores)[-k:]))
    return {"path_score": path_score, "bag_score": bag_score}


def _delta_signature(trajectory: np.ndarray) -> np.ndarray:
    if trajectory.shape[0] <= 1:
        return np.zeros((trajectory.shape[1],), dtype=float)
    deltas = np.diff(trajectory, axis=0)
    normed = np.vstack([_normalize(row) for row in deltas])
    weights = _position_weights(normed.shape[0])
    weight_sum = float(weights.sum())
    if weight_sum <= 0:
        weights = np.ones_like(weights)
        weight_sum = float(weights.sum())
    weights = weights / weight_sum
    signature = np.sum(normed * weights[:, None], axis=0)
    return _normalize(signature)


def _order_fidelity(baseline_sig: np.ndarray, trajectory: np.ndarray) -> float:
    sig = _delta_signature(trajectory)
    if sig.size == 0 or baseline_sig.size == 0:
        return 0.0
    cos = float(np.dot(baseline_sig, sig))
    return 0.5 * (1.0 + cos)


def _shuffle(emb: np.ndarray, roles: List[str], rng: random.Random) -> Tuple[np.ndarray, List[str]]:
    idxs = list(range(len(roles)))
    rng.shuffle(idxs)
    return emb[idxs], [roles[i] for i in idxs]


def _drop_k_strong(
    emb: np.ndarray, roles: List[str], query: np.ndarray, k: int
) -> Tuple[np.ndarray, List[str]]:
    n = len(roles)
    if k <= 0 or n <= 1:
        return emb, roles
    k = min(k, n - 1)
    normed = np.vstack([_normalize(row) for row in emb])
    q = _normalize(query)
    scores = (normed @ q) * _role_weights(roles)
    drop_idx = set(np.argsort(scores)[-k:])
    keep_idx = [i for i in range(n) if i not in drop_idx]
    return emb[keep_idx], [roles[i] for i in keep_idx]


def _drop_k_random(
    emb: np.ndarray, roles: List[str], k: int, rng: random.Random
) -> Tuple[np.ndarray, List[str]]:
    n = len(roles)
    if k <= 0 or n <= 1:
        return emb, roles
    k = min(k, n - 1)
    drop_idx = set(rng.sample(range(n), k))
    keep_idx = [i for i in range(n) if i not in drop_idx]
    return emb[keep_idx], [roles[i] for i in keep_idx]


def _truncate_head(emb: np.ndarray, roles: List[str], k: int) -> Tuple[np.ndarray, List[str]]:
    if k <= 0 or len(roles) <= 1:
        return emb, roles
    return emb[k:], roles[k:]


def _truncate_tail(emb: np.ndarray, roles: List[str], k: int) -> Tuple[np.ndarray, List[str]]:
    if k <= 0 or len(roles) <= 1:
        return emb, roles
    return emb[: -k], roles[: -k]


def _role_noise(roles: List[str], rate: float, rng: random.Random) -> List[str]:
    noisy = []
    for role in roles:
        if rng.random() < rate:
            noisy.append("memory")
        else:
            noisy.append(role)
    return noisy


def _trace_noise(emb: np.ndarray, sigma: float, rng: np.random.RandomState) -> np.ndarray:
    if sigma <= 0:
        return emb
    noise = rng.normal(0.0, sigma, size=emb.shape)
    return emb + noise


def _permute_dims(emb: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    perm = rng.permutation(emb.shape[1])
    return emb[:, perm]


def _random_trace(emb: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
    mean = float(np.mean(emb))
    std = float(np.std(emb)) if float(np.std(emb)) > 0 else 1.0
    return rng.normal(mean, std, size=emb.shape)


def _monotonic_drop(drops: List[float]) -> bool:
    for prev, nxt in zip(drops, drops[1:]):
        if nxt + 1e-6 < prev:
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Falsify a capsule trajectory by applying corruptions.")
    parser.add_argument("path", help="Path to a capsule JSON file.")
    parser.add_argument("--query", help="Probe query text (defaults to last user turn).")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed.")
    parser.add_argument("--drop-k", default="1,2,3", help="Comma-separated drop counts.")
    parser.add_argument("--truncate-head", default="1", help="Comma-separated head truncations.")
    parser.add_argument("--truncate-tail", default="1", help="Comma-separated tail truncations.")
    parser.add_argument("--role-noise", type=float, default=0.35, help="Role noise rate.")
    parser.add_argument("--trace-noise", type=float, default=0.08, help="Gaussian noise sigma.")
    parser.add_argument("--top-k", type=int, default=3, help="Top-k turns for bag score.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    np_rng = np.random.RandomState(args.seed)

    payload = _load_capsule(Path(args.path))
    trajectory, roles = _extract_trajectory(payload)
    if trajectory.shape[0] == 0:
        raise SystemExit("No trajectory entries to score.")
    expected_dim = trajectory.shape[1]

    cfg = FRAMConfig.from_env()
    backend = normalize_cognitive_backend(
        (payload.get("writer_config") or {}).get("embedding_backend")
        or getattr(cfg, "cognitive_memory_embedding_backend", "hashing")
    )

    query_text = args.query or _default_query(payload)
    if not query_text:
        raise SystemExit("No query provided and no user turn found in capsule.")
    query_vec = _embed_query(query_text, cfg=cfg, backend=backend, expected_dim=expected_dim)

    baseline = _score_alignment(query_vec, trajectory, roles, top_k=args.top_k)
    baseline_sig = _delta_signature(trajectory)
    baseline_score = baseline["path_score"]

    variants: List[Dict[str, Any]] = []

    def _add_variant(name: str, emb: np.ndarray, role_list: List[str]) -> None:
        scores = _score_alignment(query_vec, emb, role_list, top_k=args.top_k)
        order_fidelity = _order_fidelity(baseline_sig, emb)
        length_factor = float(emb.shape[0]) / float(trajectory.shape[0])
        combined = scores["path_score"] * order_fidelity * length_factor
        variants.append(
            {
                "name": name,
                "query_score": scores["path_score"],
                "bag_score": scores["bag_score"],
                "order_fidelity": order_fidelity,
                "length_factor": length_factor,
                "combined_score": combined,
                "drop": baseline_score - combined,
                "turns": int(emb.shape[0]),
            }
        )

    shuffled_emb, shuffled_roles = _shuffle(trajectory, roles, rng)
    _add_variant("shuffle_order", shuffled_emb, shuffled_roles)

    noisy_roles = _role_noise(roles, args.role_noise, rng)
    _add_variant("role_noise", trajectory, noisy_roles)

    trace_noisy = _trace_noise(trajectory, args.trace_noise, np_rng)
    _add_variant("trace_noise", trace_noisy, roles)

    permuted = _permute_dims(trajectory, np_rng)
    _add_variant("permute_dims", permuted, roles)

    random_trace = _random_trace(trajectory, np_rng)
    _add_variant("random_trace", random_trace, roles)

    drop_k_values = [int(val) for val in args.drop_k.split(",") if val.strip()]
    drop_k_values = sorted({max(0, val) for val in drop_k_values})
    drop_drops: List[float] = []
    drop_random_drops: List[float] = []
    for k in drop_k_values:
        emb_drop, roles_drop = _drop_k_strong(trajectory, roles, query_vec, k)
        name = f"drop_k_{k}"
        scores = _score_alignment(query_vec, emb_drop, roles_drop, top_k=args.top_k)
        order_fidelity = _order_fidelity(baseline_sig, emb_drop)
        length_factor = float(emb_drop.shape[0]) / float(trajectory.shape[0])
        combined = scores["path_score"] * order_fidelity * length_factor
        drop = baseline_score - combined
        drop_drops.append(drop)
        variants.append(
            {
                "name": name,
                "query_score": scores["path_score"],
                "bag_score": scores["bag_score"],
                "order_fidelity": order_fidelity,
                "length_factor": length_factor,
                "combined_score": combined,
                "drop": drop,
                "turns": int(emb_drop.shape[0]),
            }
        )
        emb_rand, roles_rand = _drop_k_random(trajectory, roles, k, rng)
        name_random = f"drop_k_random_{k}"
        scores_rand = _score_alignment(query_vec, emb_rand, roles_rand, top_k=args.top_k)
        order_fidelity_rand = _order_fidelity(baseline_sig, emb_rand)
        length_factor_rand = float(emb_rand.shape[0]) / float(trajectory.shape[0])
        combined_rand = scores_rand["path_score"] * order_fidelity_rand * length_factor_rand
        drop_rand = baseline_score - combined_rand
        drop_random_drops.append(drop_rand)
        variants.append(
            {
                "name": name_random,
                "query_score": scores_rand["path_score"],
                "bag_score": scores_rand["bag_score"],
                "order_fidelity": order_fidelity_rand,
                "length_factor": length_factor_rand,
                "combined_score": combined_rand,
                "drop": drop_rand,
                "turns": int(emb_rand.shape[0]),
            }
        )

    head_vals = [int(val) for val in args.truncate_head.split(",") if val.strip()]
    for k in sorted({max(0, val) for val in head_vals}):
        emb_head, roles_head = _truncate_head(trajectory, roles, k)
        _add_variant(f"truncate_head_{k}", emb_head, roles_head)

    tail_vals = [int(val) for val in args.truncate_tail.split(",") if val.strip()]
    for k in sorted({max(0, val) for val in tail_vals}):
        emb_tail, roles_tail = _truncate_tail(trajectory, roles, k)
        _add_variant(f"truncate_tail_{k}", emb_tail, roles_tail)

    variants_sorted = sorted(variants, key=lambda item: item["drop"], reverse=True)
    max_drop_name = variants_sorted[0]["name"] if variants_sorted else None

    verdict = {
        "drop_k_monotonic_targeted": _monotonic_drop(drop_drops) if drop_drops else None,
        "drop_k_monotonic_random": _monotonic_drop(drop_random_drops) if drop_random_drops else None,
        "largest_drop_variant": max_drop_name,
        "largest_drop_is_strong_corruption": max_drop_name in {
            "shuffle_order",
            "random_trace",
            "permute_dims",
        },
    }

    output = {
        "capsule_id": payload.get("capsule_id"),
        "capsule_path": str(Path(args.path)),
        "query": query_text,
        "backend": backend,
        "config": {
            "drop_k_targeted_strategy": "drop_high_similarity",
            "drop_k_random_strategy": "random",
            "role_noise_rate": args.role_noise,
            "trace_noise_sigma": args.trace_noise,
            "top_k": args.top_k,
        },
        "baseline": {
            "query_score": baseline["path_score"],
            "bag_score": baseline["bag_score"],
            "combined_score": baseline_score,
            "order_fidelity": 1.0,
            "length_factor": 1.0,
        },
        "variants": variants_sorted,
        "verdict": verdict,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"capsule_id: {output['capsule_id']}")
        print(f"query: {output['query']}")
        print(f"backend: {output['backend']}")
        print(f"baseline_query_score: {baseline['path_score']:.4f}")
        print(f"baseline_combined_score: {baseline_score:.4f}")
        print(f"baseline_bag_score: {baseline['bag_score']:.4f}")
        print("variants:")
        for item in variants_sorted:
            print(
                f"  {item['name']}: combined={item['combined_score']:.4f} "
                f"query={item['query_score']:.4f} bag={item['bag_score']:.4f} "
                f"drop={item['drop']:.4f} turns={item['turns']}"
            )
        print("verdict:")
        for key, value in verdict.items():
            print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
