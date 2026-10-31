from __future__ import annotations

"""
Env-driven autolog helper for F‑RAM cognitive memory.

Usage (from any Python environment):

  from tools.autolog_env import autolog_turn
  autolog_turn(user_text, assistant_text, session_id="my-session", topic="chat")

If the environment variable COGMEM_AUTOLOG is set to a truthy value ("1", "true",
"yes"), this will append the two turns to the cognitive memory store using the same
segmented, idempotent writer as tools/log_chat_turn.py. If COGMEM_AUTOLOG is not set,
the call is a no-op so it is safe to include unconditionally.

This module avoids subprocesses and writes directly via CognitiveMemoryStore.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def _truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_tags(value: Optional[str]) -> list[str]:
    if not value:
        return []
    raw = str(value).replace(",", " ").strip()
    if not raw:
        return []
    tags = [chunk.strip().lower() for chunk in raw.split() if chunk.strip()]
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return deduped


def autolog_turn(
    user: Optional[str],
    assistant: Optional[str],
    *,
    session_id: Optional[str] = None,
    topic: Optional[str] = None,
    created_at: Optional[str] = None,
) -> None:
    """Append a user+assistant turn to cognitive memory if COGMEM_AUTOLOG is enabled.

    - session_id defaults to $COGMEM_SESSION_ID or "default".
    - timestamps default to now (UTC) and are applied to both entries if provided.
    - topic is stored in metadata when given.
    """
    if not _truthy(os.getenv("COGMEM_AUTOLOG")):
        return

    cfg = FRAMConfig.from_env()
    # Optional test/dev override: COGMEM_STORAGE_ROOT
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if override_root:
        cfg = cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)

    session = session_id or os.getenv("COGMEM_SESSION_ID") or "default"
    stamp = created_at or datetime.now(timezone.utc).isoformat()

    meta = {}
    if topic:
        meta["topic"] = topic
    tags = _parse_tags(os.getenv("COGMEM_TAGS"))
    if tags:
        meta["tags"] = tags

    pair_id = os.getenv("COGMEM_PAIR_ID") or None

    if user:
        store.append_belief(
            text=str(user),
            role="user",
            session_id=session,
            pair_id=pair_id,
            created_at=stamp,
            metadata=meta or None,
        )
    if assistant:
        store.append_belief(
            text=str(assistant),
            role="assistant",
            session_id=session,
            pair_id=pair_id,
            created_at=stamp,
            metadata=meta or None,
        )
