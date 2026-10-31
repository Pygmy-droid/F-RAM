"""Latency and memory estimators (spec §20)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EstimationInput:
    k: int
    L: int
    m: int
    r: int
    prototypes: int
    dim: int
    bytes_per_value: int = 2  # fp16 by default
    ann_ms: float = 1.0
    projection_ms: float = 0.05
    local_probe_ms: float = 0.2
    rerank_ms: float = 2.0


def estimate_latency(inp: EstimationInput) -> float:
    base = inp.ann_ms
    projection = inp.k * inp.projection_ms
    local = inp.k * inp.L * inp.local_probe_ms
    rerank = inp.m * inp.rerank_ms
    return float(base + projection + local + rerank)


def estimate_memory_mib(inp: EstimationInput) -> float:
    proto_mem = inp.prototypes * inp.dim * inp.bytes_per_value
    subspace_mem = inp.prototypes * inp.dim * inp.r * inp.bytes_per_value
    return float((proto_mem + subspace_mem) / (1024 * 1024))


def estimate_latency_and_memory(inp: EstimationInput) -> dict[str, float]:
    return {
        "latency_ms": estimate_latency(inp),
        "memory_mib": estimate_memory_mib(inp),
    }
