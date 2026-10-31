from __future__ import annotations

import hashlib
from typing import List, Sequence, Tuple

import numpy as np

from .fractal_types import (
    DEFAULT_QUATERNION,
    FractalSeed,
    TraceLine,
    TraceNode,
    TRACE_VERSION,
)


class FractalGenerator:
    """Generate deterministic fractal trace lines for cognitive episodes."""

    def __init__(
        self,
        embedding_dim: int,
        *,
        n_nodes: int = 256,
        meso_stride: int = 4,
        macro_stride: int = 16,
    ) -> None:
        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be positive")
        if n_nodes <= 1:
            raise ValueError("n_nodes must be greater than one")
        self.embedding_dim = int(embedding_dim)
        self.n_nodes = int(n_nodes)
        self.meso_stride = max(1, int(meso_stride))
        self.macro_stride = max(1, int(macro_stride))
        self._global_projection_seed = 1_337_337

    def _seed_value(self, seed: FractalSeed) -> int:
        vector = seed.vector()
        buffer = np.asarray(vector, dtype=np.float32).tobytes()
        digest = hashlib.blake2s(digest_size=16)
        digest.update(seed.episode_id.encode("utf-8"))
        digest.update(str(seed.timestamp_ms).encode("utf-8"))
        digest.update(buffer)
        return int.from_bytes(digest.digest()[:8], "big")

    def _rng(self, value: int) -> np.random.RandomState:
        return np.random.RandomState(int(value) & 0x7FFFFFFF)

    def _stable_projection(self, rng: np.random.RandomState, d_in: int, d_out: int) -> np.ndarray:
        matrix = rng.normal(0.0, 1.0 / np.sqrt(max(d_in, 1)), size=(d_in, d_out))
        q, _ = np.linalg.qr(matrix)
        return q[:, :d_out]

    def _ifs_params(
        self, rng: np.random.RandomState, maps: int = 4
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        transforms: List[np.ndarray] = []
        offsets: List[np.ndarray] = []
        for _ in range(maps):
            base, _ = np.linalg.qr(rng.normal(size=(6, 6)))
            scale = 0.55 + 0.15 * float(rng.rand())
            transforms.append(scale * base)
            offsets.append(rng.normal(0.0, 0.25, size=(6,)))
        return transforms, offsets

    def _ifs_order(self, rng: np.random.RandomState, count: int = 8) -> List[int]:
        order = list(range(count))
        rng.shuffle(order)
        if count < 4:
            return order
        return order + order[::-1]

    def _label_for_index(self, index: int) -> str:
        if index % self.macro_stride == 0:
            return "macro"
        if index % self.meso_stride == 0:
            return "meso"
        return "micro"

    @staticmethod
    def _coord6_to_vec3(coord6: np.ndarray) -> np.ndarray:
        """Project 6-D node coords to 3-D using a deterministic pairwise mean."""
        return np.array(
            [
                0.5 * (coord6[0] + coord6[3]),
                0.5 * (coord6[1] + coord6[4]),
                0.5 * (coord6[2] + coord6[5]),
            ],
            dtype=float,
        )

    @staticmethod
    def _unit_vector(vec: np.ndarray, *, eps: float = 1e-12) -> np.ndarray | None:
        norm = float(np.linalg.norm(vec))
        if norm <= eps:
            return None
        return vec / norm

    @staticmethod
    def _quat_from_direction(direction: np.ndarray | None) -> Tuple[float, float, float, float]:
        if direction is None:
            return DEFAULT_QUATERNION
        axis = np.array([1.0, 0.0, 0.0], dtype=float)
        d = np.asarray(direction, dtype=float)
        dot = float(np.clip(np.dot(axis, d), -1.0, 1.0))
        if dot < -0.999999:
            ortho = np.array([0.0, 1.0, 0.0], dtype=float)
            if abs(float(np.dot(ortho, d))) > 0.9:
                ortho = np.array([0.0, 0.0, 1.0], dtype=float)
            ortho = ortho / float(np.linalg.norm(ortho))
            return (0.0, float(ortho[0]), float(ortho[1]), float(ortho[2]))
        v = np.cross(axis, d)
        w = 1.0 + dot
        q_raw = np.array([w, v[0], v[1], v[2]], dtype=float)
        norm = float(np.linalg.norm(q_raw))
        if norm <= 1e-12:
            return DEFAULT_QUATERNION
        q = q_raw / norm
        return (float(q[0]), float(q[1]), float(q[2]), float(q[3]))

    @staticmethod
    def _logistic_seed(seed_id: str, index: int) -> float:
        key = f"{seed_id}:{index}"
        digest = hashlib.blake2s(key.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        denom = float(2**64)
        return (value + 0.5) / denom

    @classmethod
    def _logistic_lambda(cls, seed_id: str, index: int) -> float:
        r = 3.99
        x = cls._logistic_seed(seed_id, index)
        x = r * x * (1.0 - x)
        if x <= 0.0:
            return 1e-12
        if x >= 1.0:
            return 1.0 - 1e-12
        return float(x)

    def generate(self, seed: FractalSeed) -> TraceLine:
        """Create a deterministic trace line for the provided seed."""
        vector = seed.vector()
        if vector.size != self.embedding_dim:
            raise ValueError(
                f"seed embedding has dimension {vector.size}, expected {self.embedding_dim}"
            )

        root_seed = self._seed_value(seed)
        root_rng = self._rng(root_seed)
        proj_seed = int(root_rng.randint(0, 2**31 - 1))
        ifs_seed = int(root_rng.randint(0, 2**31 - 1))
        order_seed = int(root_rng.randint(0, 2**31 - 1))

        projection = self._stable_projection(self._rng(proj_seed), self.embedding_dim, 6)
        transforms, offsets = self._ifs_params(self._rng(ifs_seed))
        order = self._ifs_order(self._rng(order_seed), len(transforms))

        coords: List[np.ndarray] = []
        labels: List[str] = []
        arcs: List[float] = []
        state = np.asarray(vector @ projection, dtype=float)
        arc = 0.0

        for index in range(self.n_nodes):
            transform = transforms[order[index % len(order)]]
            offset = offsets[order[index % len(order)]]
            state = transform @ state + offset
            if coords:
                arc += float(np.linalg.norm(state - coords[-1]))
            label = self._label_for_index(index)
            coords.append(state.copy())
            labels.append(label)
            arcs.append(float(arc))

        p3 = [self._coord6_to_vec3(coord) for coord in coords]
        directions: List[np.ndarray | None] = []
        for idx in range(len(p3)):
            if len(p3) == 1:
                directions.append(None)
            elif idx < len(p3) - 1:
                directions.append(self._unit_vector(p3[idx + 1] - p3[idx]))
            else:
                directions.append(self._unit_vector(p3[idx] - p3[idx - 1]))

        nodes: List[TraceNode] = []
        for idx, (coord, label, arc_value) in enumerate(zip(coords, labels, arcs)):
            q_value = self._quat_from_direction(directions[idx])
            lambda_value = self._logistic_lambda(seed.episode_id, idx)
            nodes.append(
                TraceNode(
                    scale=label,
                    coord6=tuple(float(x) for x in coord),
                    s_arc=arc_value,
                    index=idx,
                    q=q_value,
                    lambda_value=lambda_value,
                )
            )

        provenance = {
            "version": TRACE_VERSION,
            "n_nodes": self.n_nodes,
            "nodes_generated": len(nodes),
            "seed_hash": f"{root_seed:016x}",
            "seed_int": root_seed,
            "meso_stride": self.meso_stride,
            "macro_stride": self.macro_stride,
            "projection_seed": proj_seed,
            "ifs_seed": ifs_seed,
            "order_seed": order_seed,
        }

        return TraceLine(seed_id=seed.episode_id, nodes=nodes, provenance=provenance)

    def project(self, embedding: Sequence[float], projection_seed: int | None = None) -> np.ndarray:
        """Project an embedding into the shared 6-D space."""
        vector = np.asarray(embedding, dtype=float).ravel()
        if vector.size != self.embedding_dim:
            raise ValueError(
                f"embedding has dimension {vector.size}, expected {self.embedding_dim}"
            )
        seed = projection_seed if projection_seed is not None else self._global_projection_seed
        basis = self._stable_projection(self._rng(seed), self.embedding_dim, 6)
        return vector @ basis

    def retrace(self, line: TraceLine) -> np.ndarray:
        """Materialise the 6-D coordinates for the supplied trace line."""
        return np.vstack([np.asarray(node.coord6, dtype=float) for node in line.nodes])
