from __future__ import annotations

from typing import Any, Dict, Tuple

_last_block: Dict[str, str] | None = None


def before_memory_write(item: Dict[str, Any]) -> Tuple[bool, str | None]:
    return True, None


def before_memory_read(query: Dict[str, Any]) -> Tuple[bool, str | None]:
    return True, None


def before_shortlist(candidate_list: list[Dict[str, Any]]) -> Tuple[bool, str | None]:
    return True, None


def record_block(hook: str, reason: str | None) -> None:
    global _last_block
    _last_block = {"hook": hook, "reason": reason or ""}


def last_block() -> Dict[str, str] | None:
    return _last_block
