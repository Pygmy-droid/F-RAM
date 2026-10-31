from __future__ import annotations

import dataclasses
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fram_core.pipeline import tokenize_text
from fram_core.rotational_lift import (
    compress_to_invariants,
    passes_reentry_bound,
    reconstruct_from_invariants,
    recursive_lift,
    recursive_reconstruct,
    reentry_distances,
)
from fram_serving.cognitive_embeddings import normalize_cognitive_backend
from fram_serving.fractal_memory import (
    DEFAULT_LAMBDA,
    DEFAULT_QUATERNION,
    TRACE_VERSION,
    FractalGenerator,
    FractalSeed,
    TraceLine,
    TraceNode,
)


CAPSULE_VERSION = "capsule-mvp-1"
REMEMBERING_DEFINITION_VERSION = 1
REMEMBERING_DEFINITION_TEXT = (
    "Remembering (system-authored, non-limiting): Remembering is not just "
    "retrieving facts. It is preserving an entire episode so it can be "
    "re-entered later and shape the present state with the same anchors, "
    "commitments, mistakes, and texture. In F-RAM terms, this means keeping "
    "the full raw transcript plus a dense trajectory of state embeddings and "
    "the geometry of that trajectory, without compression caps, so the lived "
    "path can be replayed and felt-not merely cited. This definition is a "
    "floor; the capsule stores more than we can name today, and future systems "
    "may read more from it."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _timestamp_ms(stamp: str | None) -> int:
    parsed = _parse_iso(stamp)
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    return int(parsed.timestamp() * 1000.0)


def _safe_stamp(iso_stamp: str) -> str:
    keep = []
    for ch in iso_stamp:
        if ch.isalnum():
            keep.append(ch)
    return "".join(keep) or uuid.uuid4().hex


def _resolve_git_commit() -> str | None:
    try:
        repo_root = Path(__file__).resolve().parents[1]
        head_path = repo_root / ".git" / "HEAD"
        if not head_path.exists():
            return None
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split("ref:", 1)[1].strip()
            ref_path = repo_root / ".git" / ref
            if ref_path.exists():
                commit = ref_path.read_text(encoding="utf-8").strip()
                return commit or None
            return None
        return head or None
    except Exception:
        return None


def _writer_config(config: Any, *, embedding_backend: str, embedding_dim: int | None, n_nodes: int) -> Dict[str, Any]:
    model_name = None
    if embedding_backend == "semantic":
        try:
            model_name = str(
                getattr(config, "cognitive_memory_semantic_model", "all-MiniLM-L6-v2")
            )
        except Exception:
            model_name = "all-MiniLM-L6-v2"
    return {
        "capsule_version": CAPSULE_VERSION,
        "embedding_backend": embedding_backend,
        "embedding_model": model_name,
        "embedding_dim": embedding_dim,
        "trace_nodes": int(n_nodes),
        "trace_version": TRACE_VERSION,
    }


def _trace_line_payload(line: TraceLine) -> Dict[str, Any]:
    def _node_quaternion(node: TraceNode) -> List[float]:
        raw_q = node.q
        if isinstance(raw_q, dict):
            q_vals = [
                raw_q.get("w", DEFAULT_QUATERNION[0]),
                raw_q.get("x", DEFAULT_QUATERNION[1]),
                raw_q.get("y", DEFAULT_QUATERNION[2]),
                raw_q.get("z", DEFAULT_QUATERNION[3]),
            ]
        elif isinstance(raw_q, (list, tuple)) and len(raw_q) == 4:
            q_vals = list(raw_q)
        else:
            q_vals = list(DEFAULT_QUATERNION)
        return [float(val) for val in q_vals]

    def _node_lambda(node: TraceNode) -> float:
        raw = node.lambda_value
        if raw is None:
            return float(DEFAULT_LAMBDA)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return float(DEFAULT_LAMBDA)
        if not (0.0 < value < 1.0):
            return float(DEFAULT_LAMBDA)
        return value

    return {
        "seed_id": line.seed_id,
        "nodes": [
            {
                "scale": node.scale,
                "coord6": [float(val) for val in node.coord6],
                "s_arc": float(node.s_arc),
                "index": int(node.index),
                "q": _node_quaternion(node),
                "lambda_value": _node_lambda(node),
            }
            for node in line.nodes
        ],
        "provenance": dict(line.provenance),
    }


def _rotational_lift_enrichment(
    embeddings: Sequence[np.ndarray],
    config: Any,
    *,
    parent_capsule_id: Optional[str] = None,
    own_turn_count: Optional[int] = None,
    ancestor_capsule_ids: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Populate self_invariants/open_residuals from a trajectory of embeddings
    using fram_core.rotational_lift (the "Recursive Rotational Lift"
    prototype - see docs/rotational_lift.md).

    Gated by FRAM_ROTATIONAL_LIFT_ENABLED (checked by the caller). This is a
    purely additive write-side experiment: it never affects retrieval/ranking
    in MemoryCapsuleStore.search(), and it never raises - callers treat any
    failure as "nothing computed," the same way fractal trace generation
    silently skips vectors it can't use.

    If ``parent_capsule_id`` is given (only when session lineage is also
    enabled - see ``_find_parent_capsule_id``), the first hop's
    ``LiftCapsule.parent_id`` is set to it, so the chain in this capsule's
    ``open_residuals`` literally points back at the previous capsule in the
    same session - not just descriptively, a field a caller could walk.

    ``embeddings`` may be this capsule's own turns only, or (when
    `rotational_lift_lineage_window` > 0 - see
    ``MemoryCapsuleStore._collect_ancestor_embeddings``) ancestor capsules'
    turns prepended in front of this capsule's own. ``own_turn_count`` and
    ``ancestor_capsule_ids`` are recorded in the output purely for
    provenance, so a reader can tell how much of the lifted trajectory is
    "this capsule" versus inherited session history.
    """

    trajectory = np.stack([np.asarray(vec, dtype=float).ravel() for vec in embeddings], axis=0)
    if trajectory.shape[0] < 2:
        return [], []

    if own_turn_count is None:
        own_turn_count = trajectory.shape[0]
    ancestor_ids = list(ancestor_capsule_ids or [])

    try:
        n_components = int(getattr(config, "rotational_lift_invariant_components", 3))
    except Exception:
        n_components = 3
    n_components = max(1, n_components)

    z, basis, mean = compress_to_invariants(trajectory, n_components)
    reconstructed = reconstruct_from_invariants(z, basis, mean)
    try:
        epsilon = float(getattr(config, "rotational_lift_reentry_epsilon", 0.25))
    except Exception:
        epsilon = 0.25
    distances = reentry_distances(trajectory, reconstructed)
    invariants = [
        {
            "kind": "rotational_lift_pca_invariants",
            "source": "fram_core.rotational_lift v0.3",
            "n_components": int(z.shape[1]),
            "trajectory_length": int(trajectory.shape[0]),
            "own_turn_count": int(own_turn_count),
            "ancestor_capsule_ids": ancestor_ids,
            "embedding_dim": int(trajectory.shape[1]),
            "basis": basis.tolist(),
            "mean": mean.tolist(),
            "z": z.tolist(),
            "reentry_epsilon": epsilon,
            "reentry_max_distance": float(distances.max()) if distances.size else 0.0,
            "reentry_passed": bool(passes_reentry_bound(trajectory, reconstructed, epsilon)),
        }
    ]

    try:
        hops = int(getattr(config, "rotational_lift_lift_hops", 2))
    except Exception:
        hops = 2
    hops = max(1, hops)
    target_dim = trajectory.shape[1] + hops
    final_state, capsules = recursive_lift(
        trajectory,
        target_dim=target_dim,
        window_rule="capsule_trajectory",
        residual_mode="exact",
    )
    if parent_capsule_id and capsules:
        capsules = [dataclasses.replace(capsules[0], parent_id=parent_capsule_id)] + list(capsules[1:])

    reconstructed_exact = recursive_reconstruct(final_state, capsules)
    exact_error = reentry_distances(trajectory, reconstructed_exact)
    residuals = [
        {
            "kind": "rotational_lift_chain",
            "source": "fram_core.rotational_lift v0.3",
            "target_dim": int(target_dim),
            "hops": len(capsules),
            "trajectory_length": int(trajectory.shape[0]),
            "own_turn_count": int(own_turn_count),
            "ancestor_capsule_ids": ancestor_ids,
            "final_state": final_state.tolist(),
            "capsules": [dataclasses.asdict(capsule) for capsule in capsules],
            "reconstruction_error_max": float(exact_error.max()) if exact_error.size else 0.0,
        }
    ]

    # Self-check: prove JSON-serializability now, inside this function's own
    # call site guard (write_capsule wraps this whole call in try/except). A
    # future edit that drops a .tolist()/int()/float() cast then fails *here*
    # (caught, logged, fields stay empty) rather than later at the
    # unprotected json.dump() in write_capsule, which would crash the entire
    # capsule write.
    json.dumps(invariants)
    json.dumps(residuals)
    return invariants, residuals


def _role_from_meta(meta: Dict[str, Any]) -> str:
    candidate = meta.get("role") or meta.get("speaker") or meta.get("author")
    if isinstance(candidate, str):
        role = candidate.strip().lower()
        if role in {"user", "assistant", "system", "tool", "memory"}:
            return role
    return "memory"


def _score_overlap(query_tokens: List[str], text_tokens: List[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    q_set = set(query_tokens)
    if not q_set:
        return 0.0
    t_set = set(text_tokens)
    overlap = len(q_set.intersection(t_set))
    if overlap <= 0:
        return 0.0
    return overlap / max(1, len(q_set))


def build_capsule_turns(
    *,
    memory_entries: Sequence[Dict[str, Any]] | None,
    user_text: str,
    assistant_text: str,
    timestamp: str | None,
    trace_id: str | None,
) -> List[Dict[str, Any]]:
    turns: List[Dict[str, Any]] = []
    if memory_entries:
        for entry in memory_entries:
            meta = dict(entry.get("metadata") or {})
            role = _role_from_meta(meta)
            entry_time = entry.get("time") or timestamp or _now_iso()
            meta_out = dict(meta)
            entry_id = entry.get("id")
            if entry_id:
                meta_out.setdefault("entry_id", entry_id)
            last_seen = entry.get("last_seen")
            if last_seen:
                meta_out.setdefault("last_seen", last_seen)
            turns.append(
                {
                    "role": role,
                    "text": str(entry.get("text") or ""),
                    "time": str(entry_time),
                    "meta": meta_out,
                }
            )
    if user_text:
        turns.append(
            {
                "role": "user",
                "text": str(user_text),
                "time": str(timestamp or _now_iso()),
                "meta": {"trace_id": trace_id} if trace_id else {},
            }
        )
    turns.append(
        {
            "role": "assistant",
            "text": str(assistant_text or ""),
            "time": str(timestamp or _now_iso()),
            "meta": {"trace_id": trace_id} if trace_id else {},
        }
    )
    return turns


class MemoryCapsuleStore:
    """Append-only capsule store capturing raw transcript + trajectory + geometry."""

    def __init__(self, root: Path, *, config: Any) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._config = config
        self._logger = logging.getLogger("fram.memory_capsule")

    def _iter_capsule_paths(self) -> List[Path]:
        paths = list(self.root.glob("capsule_*.json"))
        paths.sort(reverse=True)
        return paths

    def _load_capsule(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning("Memory capsule read failed (%s): %s", path, exc)
            return None
        if not isinstance(payload, dict):
            self._logger.warning("Memory capsule payload is not a JSON object (%s)", path)
            return None
        return payload

    def _find_parent_capsule_id(self, session_id: str) -> Optional[str]:
        """Most recent existing capsule sharing ``session_id``, if any.

        `_iter_capsule_paths` already returns paths newest-first (filenames
        are stamped with a sortable ISO timestamp), so the first match is the
        immediate predecessor in this session - not necessarily written by
        this same process/run.

        Bounded by `capsule_session_lineage_scan_limit` (default 500): an
        append-only, uncapped capsule store (`docs/memory_capsule.md`'s
        "no-ceiling" design) would otherwise make every write's lineage
        lookup slower as the store grows, unboundedly. A cheap substring
        pre-check on the raw file text (matching this file's own
        `json.dump(..., indent=2)` key formatting) skips a full JSON parse
        for the common case of a non-matching session, since capsule
        payloads can be large (embeddings, fractal traces).
        """

        try:
            scan_limit = int(getattr(self._config, "capsule_session_lineage_scan_limit", 500))
        except Exception:
            scan_limit = 500
        scan_limit = max(1, scan_limit)
        needle = f'"session_id": {json.dumps(session_id)}'

        scanned = 0
        for path in self._iter_capsule_paths():
            if scanned >= scan_limit:
                self._logger.info(
                    "Capsule session lineage scan limit (%d) reached for session_id=%s "
                    "without finding a parent",
                    scan_limit,
                    session_id,
                )
                break
            scanned += 1
            try:
                raw = path.read_text(encoding="utf-8")
            except Exception as exc:
                self._logger.warning("Memory capsule read failed (%s): %s", path, exc)
                continue
            if needle not in raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception as exc:
                self._logger.warning("Memory capsule read failed (%s): %s", path, exc)
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("session_id") == session_id:
                candidate = payload.get("capsule_id")
                if isinstance(candidate, str) and candidate:
                    return candidate
        return None

    def _load_capsule_by_id(self, capsule_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific capsule by id via a targeted filename glob.

        Unlike `_find_parent_capsule_id`, this does not scan/parse every
        capsule - the capsule id is embedded in the filename
        (`capsule_<stamp>_<capsule_id>.json`), so this is a direct lookup.
        """

        matches = list(self.root.glob(f"capsule_*_{capsule_id}.json"))
        if not matches:
            return None
        return self._load_capsule(matches[0])

    def _collect_ancestor_embeddings(
        self, parent_capsule_id: str, window: int, expected_dim: int
    ) -> Tuple[List[np.ndarray], List[str]]:
        """Walk back up to ``window`` ancestor capsules via each capsule's own
        recorded "continues" link (not a store-wide scan - `_load_capsule_by_id`
        is a direct filename lookup per hop), collecting their raw per-turn
        trajectory embeddings, oldest ancestor first.

        Ancestor turns whose embedding dimension doesn't match
        ``expected_dim`` (e.g. the store was ever reconfigured with a
        different embedding backend) are silently skipped, not fatal - this
        mirrors how `write_capsule` already skips dimension-mismatched
        vectors when building its own fractal trace stack.
        """

        chain: List[Dict[str, Any]] = []
        current_id: Optional[str] = parent_capsule_id
        for _ in range(max(0, window)):
            if not current_id:
                break
            payload = self._load_capsule_by_id(current_id)
            if payload is None:
                break
            chain.append(payload)
            current_id = None
            for link in payload.get("links") or []:
                if isinstance(link, dict) and link.get("kind") == "continues":
                    candidate = link.get("target_capsule_id")
                    if isinstance(candidate, str) and candidate:
                        current_id = candidate
                        break

        ancestor_embeddings: List[np.ndarray] = []
        ancestor_ids: List[str] = []
        for payload in reversed(chain):  # oldest ancestor first
            contributed = False
            for entry in payload.get("trajectory") or []:
                vec = entry.get("embedding")
                if not isinstance(vec, list) or not vec:
                    continue
                arr = np.asarray(vec, dtype=float).ravel()
                if arr.size != expected_dim:
                    continue
                ancestor_embeddings.append(arr)
                contributed = True
            # Only record this ancestor's id if it actually contributed at
            # least one embedding - otherwise ancestor_capsule_ids would
            # claim provenance for turns that were silently dimension-skipped
            # and never made it into the combined trajectory.
            if not contributed:
                continue
            capsule_id = payload.get("capsule_id")
            if isinstance(capsule_id, str) and capsule_id:
                ancestor_ids.append(capsule_id)
        return ancestor_embeddings, ancestor_ids

    @staticmethod
    def _capsule_backend(payload: Dict[str, Any]) -> Optional[str]:
        writer_cfg = payload.get("writer_config") or {}
        backend = writer_cfg.get("embedding_backend")
        if isinstance(backend, str) and backend.strip():
            return backend.strip().lower()
        trajectory = payload.get("trajectory") or []
        if trajectory:
            candidate = trajectory[0].get("embedding_backend")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip().lower()
        return None

    def write_capsule(
        self,
        *,
        turns: Sequence[Dict[str, Any]],
        session_id: str | None = None,
        source: Dict[str, Any] | None = None,
        vectorizer: Any | None = None,
        vectorizer_backend: str | None = None,
        created_at: str | None = None,
        self_invariants: Optional[List[Dict[str, Any]]] = None,
        open_residuals: Optional[List[Dict[str, Any]]] = None,
        links: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        capsule_id = uuid.uuid4().hex
        created_at_iso = created_at or _now_iso()
        raw_transcript: List[Dict[str, Any]] = []
        for idx, turn in enumerate(turns):
            role = str(turn.get("role") or "unknown").strip().lower() or "unknown"
            text = str(turn.get("text") or "")
            time_value = turn.get("time") or created_at_iso
            meta = dict(turn.get("meta") or {})
            raw_transcript.append(
                {
                    "index": idx,
                    "role": role,
                    "text": text,
                    "time": str(time_value),
                    "meta": meta,
                }
            )

        backend = vectorizer_backend or normalize_cognitive_backend(
            getattr(self._config, "cognitive_memory_embedding_backend", "hashing")
        )
        trajectory: List[Dict[str, Any]] = []
        embeddings: List[np.ndarray] = []
        if vectorizer is not None and raw_transcript:
            try:
                texts = [entry["text"] for entry in raw_transcript]
                matrix = vectorizer.transform(texts)
                if hasattr(matrix, "toarray"):
                    arr = matrix.toarray()
                else:
                    arr = np.asarray(matrix, dtype=float)
                arr = np.asarray(arr, dtype=float)
                if arr.ndim == 1:
                    arr = arr.reshape(1, -1)
                for idx, vec in enumerate(arr):
                    vec = np.asarray(vec, dtype=float).ravel()
                    embeddings.append(vec)
                    char_span = [0, len(raw_transcript[idx]["text"])]
                    trajectory.append(
                        {
                            "index": idx,
                            "turn_index": idx,
                            "text_ref": {"turn_index": idx, "char_span": char_span},
                            "embedding": vec.tolist(),
                            "embedding_backend": backend,
                            "time": raw_transcript[idx]["time"],
                            "notes": {},
                        }
                    )
            except Exception as exc:
                self._logger.warning("Memory capsule embedding failed: %s", exc)

        session_links: List[Dict[str, Any]] = []
        parent_capsule_id: Optional[str] = None
        if getattr(self._config, "capsule_session_lineage_enabled", False) and session_id:
            try:
                parent_capsule_id = self._find_parent_capsule_id(session_id)
            except Exception as exc:
                self._logger.warning("Capsule session lineage lookup failed: %s", exc)
            if parent_capsule_id:
                session_links.append(
                    {
                        "kind": "continues",
                        "target_capsule_id": parent_capsule_id,
                        "source": "capsule_session_lineage_v0.1",
                    }
                )

        combined_embeddings: List[np.ndarray] = list(embeddings)
        own_turn_count = len(embeddings)
        ancestor_capsule_ids: List[str] = []
        if (
            getattr(self._config, "rotational_lift_enabled", False)
            and parent_capsule_id
            and embeddings
        ):
            try:
                lineage_window = int(getattr(self._config, "rotational_lift_lineage_window", 0))
            except Exception:
                lineage_window = 0
            if lineage_window > 0:
                try:
                    ancestor_embeddings, ancestor_capsule_ids = self._collect_ancestor_embeddings(
                        parent_capsule_id, lineage_window, int(embeddings[0].size)
                    )
                except Exception as exc:
                    self._logger.warning("Rotational lift ancestor lookup failed: %s", exc)
                    ancestor_embeddings, ancestor_capsule_ids = [], []
                combined_embeddings = ancestor_embeddings + list(embeddings)

        rotational_lift_invariants: List[Dict[str, Any]] = []
        rotational_lift_residuals: List[Dict[str, Any]] = []
        if getattr(self._config, "rotational_lift_enabled", False) and len(combined_embeddings) >= 2:
            try:
                rotational_lift_invariants, rotational_lift_residuals = _rotational_lift_enrichment(
                    combined_embeddings,
                    self._config,
                    parent_capsule_id=parent_capsule_id,
                    own_turn_count=own_turn_count,
                    ancestor_capsule_ids=ancestor_capsule_ids,
                )
            except Exception as exc:
                self._logger.warning("Rotational lift enrichment failed: %s", exc)

        trace_stack: List[Dict[str, Any]] = []
        fractal_payload: Dict[str, Any] = {
            "trace_version": TRACE_VERSION,
            "embedding_dim": None,
            "trace_stack": trace_stack,
        }
        embed_dim: int | None = None
        n_nodes = 0
        if embeddings:
            embed_dim = int(embeddings[0].size)
            fractal_payload["embedding_dim"] = embed_dim
            try:
                n_nodes = int(
                    getattr(self._config, "fractal_downsample_target", 256)
                )
            except Exception:
                n_nodes = 256
            if n_nodes <= 1:
                n_nodes = 256
            generator = FractalGenerator(embed_dim, n_nodes=n_nodes)
            for idx, vec in enumerate(embeddings):
                if vec.size != embed_dim:
                    continue
                seed_id = f"{capsule_id}:{idx}"
                seed = FractalSeed(
                    episode_id=seed_id,
                    timestamp_ms=_timestamp_ms(raw_transcript[idx]["time"]),
                    embedding=vec,
                    metadata={
                        "capsule_id": capsule_id,
                        "turn_index": idx,
                        "role": raw_transcript[idx]["role"],
                    },
                )
                line = generator.generate(seed)
                trace_stack.append(
                    {
                        "index": idx,
                        "trajectory_index": idx,
                        "trace_line": _trace_line_payload(line),
                    }
                )

        payload: Dict[str, Any] = {
            "capsule_id": capsule_id,
            "capsule_version": CAPSULE_VERSION,
            "created_at": created_at_iso,
            "session_id": session_id,
            "commit": _resolve_git_commit(),
            "source": source
            or {
                "kind": "live",
                "tool": "fram_serving",
                "version": CAPSULE_VERSION,
            },
            "writer_config": _writer_config(
                self._config,
                embedding_backend=backend,
                embedding_dim=embed_dim,
                n_nodes=n_nodes or 0,
            ),
            "raw_transcript": raw_transcript,
            "trajectory": trajectory,
            "fractal": fractal_payload,
            "self_invariants": list(self_invariants or []) + rotational_lift_invariants,
            "remembering_definition": {
                "text": REMEMBERING_DEFINITION_TEXT,
                "time": created_at_iso,
                "version": REMEMBERING_DEFINITION_VERSION,
                "author": "system",
            },
            "open_residuals": list(open_residuals or []) + rotational_lift_residuals,
            "links": list(links or []) + session_links,
        }

        filename = f"capsule_{_safe_stamp(created_at_iso)}_{capsule_id}.json"
        target = self.root / filename
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self._logger.info("MEMORY CAPSULE WRITTEN -> %s", target.resolve())
        return {"capsule": payload, "path": str(target)}

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        vectorizer: Any | None = None,
        vectorizer_backend: str | None = None,
        turns_per_capsule: int = 2,
        diagnostics: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        query_text = str(query or "").strip()
        if not query_text:
            return []
        try:
            k = int(k)
        except (TypeError, ValueError):
            k = 5
        if k <= 0:
            return []
        try:
            turns_per_capsule = int(turns_per_capsule)
        except (TypeError, ValueError):
            turns_per_capsule = 2
        turns_per_capsule = max(0, turns_per_capsule)

        try:
            half_life = float(
                getattr(self._config, "memory_capsule_retrieval_half_life_hours", 72.0)
            )
        except Exception:
            half_life = 72.0
        half_life = max(half_life, 0.0)

        def _recency_weight(stamp: Any) -> float:
            if half_life <= 0.0:
                return 1.0
            dt = _parse_iso(stamp)
            if dt is None:
                return 1.0
            age_hours = max((now - dt).total_seconds() / 3600.0, 0.0)
            if age_hours <= 0:
                return 1.0
            scale = max(half_life, 1e-3)
            return 1.0 / (1.0 + age_hours / scale)

        query_tokens = tokenize_text(query_text)
        query_vec: np.ndarray | None = None
        q_norm = 0.0
        backend = normalize_cognitive_backend(
            vectorizer_backend
            or getattr(self._config, "cognitive_memory_embedding_backend", "hashing")
        )
        used_embeddings = False
        if vectorizer is not None:
            try:
                matrix = vectorizer.transform([query_text])
                if hasattr(matrix, "toarray"):
                    arr = matrix.toarray()
                else:
                    arr = np.asarray(matrix, dtype=float)
                arr = np.asarray(arr, dtype=float)
                if arr.ndim == 2:
                    arr = arr[0]
                query_vec = arr.astype(float, copy=False).ravel()
                q_norm = float(np.linalg.norm(query_vec))
                if query_vec.size > 0 and q_norm > 0.0:
                    used_embeddings = True
            except Exception:
                query_vec = None
                q_norm = 0.0

        results: List[Dict[str, Any]] = []
        total_capsules = 0
        total_turns = 0
        embedding_matches = 0
        lexical_matches = 0
        now = datetime.now(timezone.utc)
        for path in self._iter_capsule_paths():
            payload = self._load_capsule(path)
            if payload is None:
                continue
            total_capsules += 1
            capsule_id = str(payload.get("capsule_id") or "")
            created_at = payload.get("created_at")
            session_id = payload.get("session_id")
            capsule_backend = self._capsule_backend(payload)
            embedding_compatible = (
                used_embeddings
                and capsule_backend is not None
                and capsule_backend == backend
            )
            raw_turns = payload.get("raw_transcript") or []
            trajectory = payload.get("trajectory") or []
            traj_by_index: Dict[int, Dict[str, Any]] = {}
            for entry in trajectory:
                try:
                    turn_idx = int(entry.get("turn_index", entry.get("index")))
                except (TypeError, ValueError):
                    continue
                traj_by_index[turn_idx] = entry
            per_capsule: List[Dict[str, Any]] = []
            for turn in raw_turns:
                try:
                    turn_index = int(turn.get("index"))
                except (TypeError, ValueError):
                    continue
                text = str(turn.get("text") or "")
                if not text.strip():
                    continue
                total_turns += 1
                role = str(turn.get("role") or "memory").strip().lower() or "memory"
                stamp = turn.get("time") or created_at
                score_raw = 0.0
                match_type = "lexical"
                if embedding_compatible and query_vec is not None and q_norm > 0.0:
                    traj_entry = traj_by_index.get(turn_index)
                    embedding = traj_entry.get("embedding") if traj_entry else None
                    if isinstance(embedding, (list, tuple)) and embedding:
                        vec = np.asarray(embedding, dtype=float).ravel()
                        if vec.size == query_vec.size:
                            v_norm = float(np.linalg.norm(vec))
                            if v_norm > 0.0:
                                score_raw = float(np.dot(query_vec, vec) / (q_norm * v_norm))
                                match_type = "embedding"
                if score_raw <= 0.0:
                    tokens = tokenize_text(text)
                    score_raw = _score_overlap(query_tokens, tokens)
                    match_type = "lexical"
                if score_raw <= 0.0:
                    continue
                recency = _recency_weight(stamp)
                score = score_raw * recency
                if match_type == "embedding":
                    embedding_matches += 1
                else:
                    lexical_matches += 1
                per_capsule.append(
                    {
                        "capsule_id": capsule_id,
                        "capsule_path": str(path),
                        "capsule_created_at": created_at,
                        "session_id": session_id,
                        "turn_index": turn_index,
                        "role": role,
                        "text": text,
                        "time": stamp,
                        "score": score,
                        "score_raw": score_raw,
                        "recency_weight": recency,
                        "match_type": match_type,
                        "embedding_backend": capsule_backend,
                    }
                )
            if turns_per_capsule > 0 and per_capsule:
                per_capsule.sort(key=lambda item: item["score"], reverse=True)
                results.extend(per_capsule[:turns_per_capsule])

        results.sort(key=lambda item: item["score"], reverse=True)
        final = results[:k]
        if diagnostics is not None:
            diagnostics.update(
                {
                    "capsules_scanned": total_capsules,
                    "turns_scanned": total_turns,
                    "embedding_backend": backend,
                    "embedding_matches": embedding_matches,
                    "lexical_matches": lexical_matches,
                    "returned": len(final),
                }
            )
        return final
