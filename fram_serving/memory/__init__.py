"""
Phase E retention/forgetting scaffolding layered atop the legacy memory module.

This package re-exports the existing memory store classes from fram_serving/memory.py
to preserve imports while hosting the new retention/forgetting helpers.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load the legacy module (fram_serving/memory.py) under a private name to avoid
# clashing with this package.
_legacy_path = Path(__file__).resolve().parent.parent / "memory.py"
_spec = importlib.util.spec_from_file_location("fram_serving._memory_legacy", _legacy_path)
assert _spec is not None and _spec.loader is not None  # for type checkers
_legacy = importlib.util.module_from_spec(_spec)
# Dataclass processing resolves annotations through sys.modules while the
# legacy module executes. Register it first, just as Python's import machinery
# does for a normal import, and avoid leaving a half-loaded module on failure.
sys.modules[_spec.name] = _legacy
try:
    _spec.loader.exec_module(_legacy)  # type: ignore[misc]
except Exception:
    sys.modules.pop(_spec.name, None)
    raise

# Re-export legacy classes/functions
CognitiveMemoryStore = _legacy.CognitiveMemoryStore
MemorySessionError = _legacy.MemorySessionError
MemoryWriteError = _legacy.MemoryWriteError
WorkingMemoryStore = _legacy.WorkingMemoryStore
register_conflict = _legacy.register_conflict
list_conflicts = _legacy.list_conflicts


def __getattr__(name: str):
    """Delegate legacy module attributes for transparent module compatibility."""

    try:
        return getattr(_legacy, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_legacy)))


# Phase E helpers
from .retention_curve import apply_retention_curve, compute_retention_score  # noqa: E402,F401
from .forgetting import apply_forgetting  # noqa: E402,F401

__all__ = [
    "CognitiveMemoryStore",
    "MemorySessionError",
    "MemoryWriteError",
    "WorkingMemoryStore",
    "register_conflict",
    "list_conflicts",
    "apply_retention_curve",
    "compute_retention_score",
    "apply_forgetting",
]
