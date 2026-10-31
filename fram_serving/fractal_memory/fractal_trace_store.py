from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from fram_serving import observability

from .fractal_gen import FractalGenerator
from .fractal_types import (
    DEFAULT_LAMBDA,
    DEFAULT_QUATERNION,
    TRACE_SCHEMA_VERSION,
    FractalSeed,
    TraceLine,
    TraceNode,
)


class FractalTraceStore:
    """Persist fractal trace lines to disk and expose retrieval helpers."""

    def __init__(
        self,
        storage_root: Path,
        *,
        observability_root: Path,
        embedding_dim: int,
        n_nodes: int = 256,
        meso_stride: int = 4,
        macro_stride: int = 16,
    ) -> None:
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.observability_root = Path(observability_root)
        self._logger = logging.getLogger("fram.fractal")
        self._observability_logged = False
        self._logger.info("FRACTAL TRACE ROOT -> %s", self.storage_root.resolve())
        self._logger.info("FRACTAL OBSERVABILITY ROOT -> %s", self.observability_root.resolve())
        self.generator = FractalGenerator(
            embedding_dim,
            n_nodes=n_nodes,
            meso_stride=meso_stride,
            macro_stride=macro_stride,
        )

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #
    def ingest_seed(self, seed: FractalSeed) -> TraceLine:
        self._log_event(
            "ingest_start",
            {
                "episode_id": seed.episode_id,
                "timestamp_ms": seed.timestamp_ms,
            },
        )
        line = self.generator.generate(seed)
        self._persist(line, seed.metadata)
        complete_payload = {
            "episode_id": seed.episode_id,
            "nodes": len(line.nodes),
            "timestamp_ms": seed.timestamp_ms,
        }
        seed_hash = line.provenance.get("seed_hash") if isinstance(line.provenance, dict) else None
        if seed_hash is not None:
            complete_payload["seed_hash"] = seed_hash
        self._log_event("ingest_complete", complete_payload)
        return line

    def _persist(self, line: TraceLine, metadata: Dict[str, object]) -> None:
        def _node_quaternion(node: TraceNode) -> Dict[str, float]:
            raw = node.q
            if isinstance(raw, dict):
                w = raw.get("w", DEFAULT_QUATERNION[0])
                x = raw.get("x", DEFAULT_QUATERNION[1])
                y = raw.get("y", DEFAULT_QUATERNION[2])
                z = raw.get("z", DEFAULT_QUATERNION[3])
            elif isinstance(raw, (list, tuple)) and len(raw) == 4:
                w, x, y, z = raw
            else:
                w, x, y, z = DEFAULT_QUATERNION
            return {"w": float(w), "x": float(x), "y": float(y), "z": float(z)}

        def _node_lambda(node: TraceNode) -> float:
            raw = node.lambda_value
            if raw is None:
                return DEFAULT_LAMBDA
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return DEFAULT_LAMBDA
            if not (0.0 < value < 1.0):
                return DEFAULT_LAMBDA
            return value

        payload = {
            "trace_version": TRACE_SCHEMA_VERSION,
            "seed_id": line.seed_id,
            "nodes": [
                {
                    "scale": node.scale,
                    "coord6": list(node.coord6),
                    "s_arc": node.s_arc,
                    "index": node.index,
                    "q": _node_quaternion(node),
                    "lambda": _node_lambda(node),
                }
                for node in line.nodes
            ],
            "provenance": dict(line.provenance),
            "metadata": dict(metadata or {}),
        }
        target = self.storage_root / f"{line.seed_id}.json"
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        self._logger.info("FRACTAL TRACE WRITTEN -> %s", target.resolve())

    def load_raw(self, episode_id: str) -> Optional[Dict[str, object]]:
        path = self.storage_root / f"{episode_id}.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_trace(self, episode_id: str) -> Optional[Tuple[TraceLine, Dict[str, object]]]:
        raw = self.load_raw(episode_id)
        if raw is None:
            return None
        nodes: List[TraceNode] = []
        for idx, entry in enumerate(raw.get("nodes", [])):
            raw_q = entry.get("q")
            q_value: Tuple[float, float, float, float] | None = None
            if isinstance(raw_q, dict):
                q_value = (
                    float(raw_q.get("w", DEFAULT_QUATERNION[0])),
                    float(raw_q.get("x", DEFAULT_QUATERNION[1])),
                    float(raw_q.get("y", DEFAULT_QUATERNION[2])),
                    float(raw_q.get("z", DEFAULT_QUATERNION[3])),
                )
            elif isinstance(raw_q, (list, tuple)) and len(raw_q) == 4:
                q_value = tuple(float(x) for x in raw_q)
            raw_lambda = entry.get("lambda")
            lambda_value: float | None = None
            if raw_lambda is not None:
                try:
                    lambda_value = float(raw_lambda)
                except (TypeError, ValueError):
                    lambda_value = None
            nodes.append(
                TraceNode(
                    scale=str(entry.get("scale", "micro")),
                    coord6=tuple(float(x) for x in entry.get("coord6", [0.0] * 6)),
                    s_arc=float(entry.get("s_arc", 0.0)),
                    index=int(entry.get("index", idx)),
                    q=q_value,
                    lambda_value=lambda_value,
                )
            )
        line = TraceLine(
            seed_id=str(raw.get("seed_id", episode_id)),
            nodes=nodes,
            provenance=dict(raw.get("provenance", {})),
        )
        metadata = dict(raw.get("metadata", {}))
        return line, metadata

    def iter_traces(self) -> Iterator[Tuple[TraceLine, Dict[str, object]]]:
        for file_path in sorted(self.storage_root.glob("*.json")):
            bundle = self.load_trace(file_path.stem)
            if bundle is None:
                continue
            yield bundle

    def available_ids(self) -> List[str]:
        return sorted(path.stem for path in self.storage_root.glob("*.json"))

    # ------------------------------------------------------------------ #
    # Observability helpers
    # ------------------------------------------------------------------ #
    def _log_event(self, kind: str, details: Dict[str, object]) -> None:
        payload = dict(details)
        payload["kind"] = kind
        observability.log_fractal_memory_event(self.observability_root, payload)
        if not self._observability_logged:
            obs_path = (self.observability_root / "memory_fractal.jsonl").resolve()
            self._logger.info("FRACTAL OBSERVABILITY WRITTEN -> %s", obs_path)
            self._observability_logged = True
