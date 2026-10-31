"""Deterministic adapters for the Chaos Playground's supported systems.

The numerical implementations remain owned by
``fram_eval.fractal_falsification``.  This module only provides a small,
validated registry and a common simulation protocol.  Calling a registry
adapter with no burn-in preserves the legacy output exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Literal, Mapping, Sequence

import numpy as np

from fram_eval.fractal_falsification import (
    simulate_aizawa,
    simulate_henon,
    simulate_logistic_map,
    simulate_lorenz,
)

SystemKind = Literal["map", "flow"]
Simulator = Callable[..., np.ndarray]


@dataclass(frozen=True)
class SystemSpec:
    """Metadata and the canonical simulator for one supported system."""

    key: str
    kind: SystemKind
    dimension: int
    defaults: Mapping[str, float]
    simulate: Simulator


def _defaults(**values: float) -> Mapping[str, float]:
    return MappingProxyType(dict(values))


SYSTEMS: Mapping[str, SystemSpec] = MappingProxyType(
    {
        "logistic": SystemSpec(
            key="logistic",
            kind="map",
            dimension=1,
            defaults=_defaults(r=3.9),
            simulate=simulate_logistic_map,
        ),
        "henon": SystemSpec(
            key="henon",
            kind="map",
            dimension=2,
            defaults=_defaults(a=1.4, b=0.3),
            simulate=simulate_henon,
        ),
        "lorenz": SystemSpec(
            key="lorenz",
            kind="flow",
            dimension=3,
            defaults=_defaults(dt=0.01, sigma=10.0, beta=8.0 / 3.0, rho=28.0),
            simulate=simulate_lorenz,
        ),
        "aizawa": SystemSpec(
            key="aizawa",
            kind="flow",
            dimension=3,
            defaults=_defaults(
                dt=0.01,
                a=0.95,
                b=0.7,
                c=0.6,
                d=3.5,
                e=0.25,
                f=0.1,
            ),
            simulate=simulate_aizawa,
        ),
    }
)


def get_system(system: str | SystemSpec) -> SystemSpec:
    """Return a registry entry, accepting a case-insensitive key."""

    if isinstance(system, SystemSpec):
        return system
    if not isinstance(system, str):
        raise TypeError("system must be a string key or SystemSpec")
    key = system.strip().lower()
    try:
        return SYSTEMS[key]
    except KeyError as exc:
        choices = ", ".join(SYSTEMS)
        raise ValueError(f"unknown system {system!r}; expected one of: {choices}") from exc


def _coerce_initial_state(
    initial_state: float | Sequence[float],
    *,
    dimension: int,
) -> float | tuple[float, ...]:
    if dimension == 1:
        if np.isscalar(initial_state):
            value = float(initial_state)
        else:
            values = tuple(float(value) for value in initial_state)
            if len(values) != 1:
                raise ValueError("initial_state must contain exactly 1 value")
            value = values[0]
        if not np.isfinite(value):
            raise ValueError("initial_state must be finite")
        return value

    if np.isscalar(initial_state):
        raise ValueError(f"initial_state must contain exactly {dimension} values")
    values = tuple(float(value) for value in initial_state)
    if len(values) != dimension:
        raise ValueError(f"initial_state must contain exactly {dimension} values")
    if not np.isfinite(values).all():
        raise ValueError("initial_state must contain only finite values")
    return values


def simulate(
    system: str | SystemSpec,
    initial_state: float | Sequence[float],
    steps: int,
    *,
    params: Mapping[str, float] | None = None,
    burn_in: int = 0,
) -> np.ndarray:
    """Simulate a registered system and return post-update states.

    ``steps`` counts returned samples. ``burn_in`` advances the same canonical
    simulator before those samples are retained.  Parameters are merged over
    the legacy defaults and unknown parameter names are rejected.
    """

    spec = get_system(system)
    if isinstance(steps, bool) or not isinstance(steps, (int, np.integer)):
        raise TypeError("steps must be an integer")
    if isinstance(burn_in, bool) or not isinstance(burn_in, (int, np.integer)):
        raise TypeError("burn_in must be an integer")
    if steps < 0:
        raise ValueError("steps must be non-negative")
    if burn_in < 0:
        raise ValueError("burn_in must be non-negative")

    state = _coerce_initial_state(initial_state, dimension=spec.dimension)
    merged = dict(spec.defaults)
    if params is not None:
        unknown = set(params) - set(spec.defaults)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown parameters for {spec.key}: {names}")
        for name, value in params.items():
            numeric = float(value)
            if not np.isfinite(numeric):
                raise ValueError(f"parameter {name!r} must be finite")
            merged[name] = numeric

    trajectory = spec.simulate(state, int(steps) + int(burn_in), **merged)
    return trajectory[int(burn_in) :]


__all__ = [
    "SYSTEMS",
    "SystemKind",
    "SystemSpec",
    "get_system",
    "simulate",
]
