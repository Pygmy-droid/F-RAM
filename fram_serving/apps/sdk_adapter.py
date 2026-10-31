from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fram_serving.config import FRAMConfig
from fram_serving.guardrails import hooks
from fram_serving.memory import CognitiveMemoryStore


def _store(config: FRAMConfig, root: Optional[Path] = None) -> CognitiveMemoryStore:
    mem_root = root or (config.STORAGE_ROOT / config.STORAGE_SUBFOLDERS.get("memory", "memory"))
    return CognitiveMemoryStore(mem_root, config=config)


def ingest_app_event(event: Dict[str, Any], *, config: Optional[FRAMConfig] = None, root: Optional[Path] = None) -> Dict[str, Any]:
    cfg = config or FRAMConfig.from_env()
    if getattr(cfg, "enable_guardrails", False):
        allowed, reason = hooks.before_memory_write(event)
        if not allowed:
            hooks.record_block("write", reason)
            return {"status": "blocked", "reason": reason}
    store = _store(cfg, root=root)
    text = str(event.get("text") or "")
    meta = dict(event.get("metadata") or {})
    if "version_id" not in meta and event.get("id"):
        meta["version_id"] = str(event["id"])
    record = store.append_episode(query=text, answer="", domain=meta.get("domain"), task=meta.get("task"), metadata=meta)
    return {"status": "ok", "id": record.get("id")}


def ingest_app_memory(key: str, value: str, *, config: Optional[FRAMConfig] = None, root: Optional[Path] = None) -> Dict[str, Any]:
    cfg = config or FRAMConfig.from_env()
    payload = {"key": key, "value": value}
    if getattr(cfg, "enable_guardrails", False):
        allowed, reason = hooks.before_memory_write(payload)
        if not allowed:
            hooks.record_block("write", reason)
            return {"status": "blocked", "reason": reason}
    store = _store(cfg, root=root)
    record = store.append_belief(
        text=f"{key}: {value}",
        sources=[],
        domain=None,
        task=None,
        metadata={"version_id": f"app:{key}"},
    )
    return {"status": "ok", "id": record.get("id")}
