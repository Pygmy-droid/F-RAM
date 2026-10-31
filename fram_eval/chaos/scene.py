"""Small, deterministic, versioned scene memory for Chaos Playground math."""

from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, field
from typing import Any, Mapping

SCENE_SCHEMA_V1 = "fram-chaos-scene/v1"
CHAOS_MATH_V1 = "fram-chaos-math/v1"


def _dict_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


@dataclass(frozen=True)
class SceneV1:
    """Serializable inputs needed to deterministically recompute a scene."""

    system_key: str
    parameters: dict[str, float]
    initial_state: tuple[float, ...]
    steps: int
    burn_in: int = 0
    dt: float | None = None
    seed: int | None = None
    diagnostic_tolerances: dict[str, float] = field(default_factory=dict)
    rotational_encoding: dict[str, Any] = field(default_factory=dict)
    complex_c: tuple[float, float] = (0.0, 0.0)
    complex_bounds: tuple[float, float, float, float] = (-2.0, 1.0, -1.5, 1.5)
    complex_max_iter: int = 128
    camera: dict[str, Any] = field(default_factory=dict)
    colors: dict[str, Any] = field(default_factory=dict)
    density: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    notes: str = ""
    schema_version: str = SCENE_SCHEMA_V1
    math_version: str = CHAOS_MATH_V1

    def __post_init__(self) -> None:
        if self.schema_version != SCENE_SCHEMA_V1:
            raise ValueError(f"unsupported scene schema: {self.schema_version!r}")
        if self.math_version != CHAOS_MATH_V1:
            raise ValueError(f"unsupported chaos math version: {self.math_version!r}")
        if not self.system_key:
            raise ValueError("system_key must be non-empty")
        if self.steps < 0 or self.burn_in < 0:
            raise ValueError("steps and burn_in must be non-negative")
        if len(self.complex_c) != 2:
            raise ValueError("complex_c must contain real and imaginary components")
        if len(self.complex_bounds) != 4:
            raise ValueError("complex_bounds must contain four values")
        if self.complex_max_iter <= 0:
            raise ValueError("complex_max_iter must be positive")

        # Detach all mutable mappings supplied by callers.  Frozen dataclasses
        # prevent attribute replacement, not mutation through shared dicts.
        for name in (
            "parameters",
            "diagnostic_tolerances",
            "rotational_encoding",
            "camera",
            "colors",
            "density",
        ):
            object.__setattr__(self, name, _dict_copy(getattr(self, name)))
        object.__setattr__(
            self,
            "initial_state",
            tuple(float(value) for value in self.initial_state),
        )
        object.__setattr__(
            self,
            "complex_c",
            tuple(float(value) for value in self.complex_c),
        )
        object.__setattr__(
            self,
            "complex_bounds",
            tuple(float(value) for value in self.complex_bounds),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible dictionary."""

        return asdict(self)

    def to_json(self) -> str:
        """Return canonical compact JSON with stable key ordering."""

        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SceneV1":
        """Load exactly schema V1 and reject unknown or missing fields."""

        data = dict(payload)
        schema = data.get("schema_version")
        if schema != SCENE_SCHEMA_V1:
            raise ValueError(f"unsupported scene schema: {schema!r}")
        math_version = data.get("math_version")
        if math_version != CHAOS_MATH_V1:
            raise ValueError(f"unsupported chaos math version: {math_version!r}")

        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown SceneV1 fields: {names}")
        missing = {
            name
            for name, definition in cls.__dataclass_fields__.items()
            if definition.default is MISSING
            and definition.default_factory is MISSING
            and name not in data
        }
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"missing SceneV1 fields: {names}")
        return cls(**data)

    @classmethod
    def from_json(cls, payload: str) -> "SceneV1":
        """Decode a SceneV1 object from JSON."""

        decoded = json.loads(payload)
        if not isinstance(decoded, dict):
            raise ValueError("scene JSON must contain an object")
        return cls.from_dict(decoded)


__all__ = [
    "CHAOS_MATH_V1",
    "SCENE_SCHEMA_V1",
    "SceneV1",
]
