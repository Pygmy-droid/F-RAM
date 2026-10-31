from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional

# Allow importing the helper even if 'tools' isn't a package
THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
REPO_ROOT = THIS_FILE.parents[1]
for p in (str(TOOLS_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from autolog_env import autolog_turn  # type: ignore
from experiment_log import log_experiment  # type: ignore

from fram_serving.config import FRAMConfig
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.memory import WorkingMemoryStore
from fram_serving.memory_capsule import CAPSULE_VERSION, MemoryCapsuleStore, build_capsule_turns

_TAG_PREFIXES = {
    "decision": ("decision:", "@decision", "[decision]", "#decision"),
    "commitment": ("commit:", "commitment:", "@commit", "[commit]", "#commit"),
    "action": ("action:", "todo:", "@action", "@todo", "[action]", "[todo]", "#action", "#todo"),
}
_EXPERIMENT_FIELDS = {
    "experiment": "title",
    "title": "title",
    "hypothesis": "hypothesis",
    "method": "method",
    "result": "result",
    "decision": "decision",
    "metrics": "metrics",
    "notes": "notes",
}

_WARNED: set[str] = set()


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
    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return deduped


def _extract_tags(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.strip().lower()
    tags: list[str] = []
    for tag, prefixes in _TAG_PREFIXES.items():
        if any(lowered.startswith(prefix) for prefix in prefixes):
            tags.append(tag)
    return tags


def _merge_tags(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for tag in group:
            if tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)
    return merged


def _warning_path() -> Path:
    override = os.getenv("COGMEM_WARN_LOG")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "logs" / "cogmem_autolog_warnings.jsonl"


def _ack_path() -> Path:
    override = os.getenv("COGMEM_ACK_LOG")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "logs" / "fram_write_ack.jsonl"


def _emit_ack(payload: dict) -> None:
    path = _ack_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    if _truthy(os.getenv("COGMEM_ECHO_ACK")):
        print(json.dumps(payload, ensure_ascii=False))


def _warn_once(code: str, message: str, *, session_id: str) -> None:
    if code in _WARNED:
        return
    _WARNED.add(code)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "level": "WARN",
        "code": code,
        "message": message,
    }
    path = _warning_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _parse_experiment_fields(text: str) -> dict[str, str]:
    if not text:
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        label = key.strip().lower()
        if label in _EXPERIMENT_FIELDS:
            fields[_EXPERIMENT_FIELDS[label]] = value.strip()
    return fields


def _extract_experiment(user: str, assistant: str) -> dict[str, str] | None:
    for source in (user, assistant):
        fields = _parse_experiment_fields(source)
        if fields and (fields.get("title") or fields.get("decision")):
            return fields
    return None


def _maybe_override_root(cfg: FRAMConfig) -> FRAMConfig:
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if not override_root:
        return cfg
    return cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})


def _append_working(
    store: WorkingMemoryStore,
    session_id: str,
    *,
    role: str,
    text: str,
    topic: Optional[str],
    tags: list[str],
) -> None:
    if not text:
        return
    meta = {"role": role}
    if topic:
        meta["topic"] = topic
    if tags:
        meta["tags"] = tags
    store.append(session_id, text, meta)


def main() -> int:
    user = os.environ.get("COGMEM_USER_TMP", "").strip()
    assistant = os.environ.get("COGMEM_ASSISTANT_TMP", "").strip()
    session = os.environ.get("COGMEM_SESSION_ID", "default")
    working_session = os.environ.get("COGMEM_WORKING_SESSION_ID") or session
    topic = os.environ.get("COGMEM_TOPIC") or None
    env_tags = _parse_tags(os.environ.get("COGMEM_TAGS"))
    inferred_tags = _merge_tags(_extract_tags(user), _extract_tags(assistant))
    tags = _merge_tags(env_tags, inferred_tags)
    capsule_tags = _parse_tags(os.environ.get("COGMEM_CAPSULE_TAGS")) or ["decision", "commitment"]
    capsule_every_raw = os.environ.get("COGMEM_CAPSULE_EVERY_N")
    try:
        capsule_every = int(capsule_every_raw) if capsule_every_raw is not None else 1
    except (TypeError, ValueError):
        capsule_every = 1
    capsule_every = max(1, capsule_every)

    if not user and not assistant:
        return 0

    if tags:
        os.environ["COGMEM_TAGS"] = ",".join(tags)

    # Always log to cognitive memory if enabled.
    stamp = datetime.now(timezone.utc).isoformat()
    ack: dict[str, object] = {
        "fram_write": "ok",
        "timestamp": stamp,
        "session_id": session,
        "working_session_id": working_session,
        "capsule_written": False,
        "capsule_id": None,
        "capsule_path": None,
    }
    try:
        autolog_turn(user or None, assistant or None, session_id=session, topic=topic)
    except Exception as exc:
        ack["fram_write"] = "error"
        ack["error"] = f"cognitive_log_failed: {exc}"
        _emit_ack(ack)
        return 1

    if _truthy(os.getenv("COGMEM_EXPERIMENT_AUTO")) and (
        "decision" in tags or "experiment" in tags
    ):
        fields = _extract_experiment(user, assistant)
        if fields:
            log_experiment(
                title=fields.get("title") or "Auto decision",
                hypothesis=fields.get("hypothesis", ""),
                method=fields.get("method", ""),
                result=fields.get("result", ""),
                decision=fields.get("decision", ""),
                metrics=fields.get("metrics", ""),
                notes=fields.get("notes", ""),
                tags=",".join(tags),
                topic=topic,
                session_id=session,
                write_capsule=False,
                working_session_id=working_session,
            )

    # Capsule writes are optional; respect FRAM_MEMORY_CAPSULE_ENABLED.
    if not _truthy(os.getenv("FRAM_MEMORY_CAPSULE_ENABLED")):
        ack["capsule_reason"] = "capsule_disabled"
        _emit_ack(ack)
        return 0

    cfg = _maybe_override_root(FRAMConfig.from_env())
    memory_root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")

    working_store = WorkingMemoryStore(
        memory_root,
        dedupe_window_seconds=getattr(cfg, "working_memory_dedupe_window_sec", 0),
    )
    prior_entries = working_store.list(working_session)
    prior_turns = max(0, len(prior_entries)) // 2
    if capsule_every >= 25:
        _warn_once(
            "capsule_cadence_sparse",
            f"Capsule cadence is sparse (every {capsule_every} turns). Consider lowering COGMEM_CAPSULE_EVERY_N.",
            session_id=working_session,
        )
    if capsule_every == 1 and prior_turns >= 200:
        _warn_once(
            "capsule_cadence_dense",
            "Capsule cadence is very dense at high turn count. Consider COGMEM_CAPSULE_EVERY_N=3..5.",
            session_id=working_session,
        )
    turn_index = prior_turns + 1
    ack["turn_index"] = turn_index
    tag_trigger = any(tag in tags for tag in capsule_tags)
    cadence_trigger = (turn_index % capsule_every) == 0
    should_write_capsule = tag_trigger or cadence_trigger

    if not should_write_capsule:
        _append_working(
            working_store, working_session, role="user", text=user, topic=topic, tags=tags
        )
        _append_working(
            working_store,
            working_session,
            role="assistant",
            text=assistant,
            topic=topic,
            tags=tags,
        )
        ack["capsule_reason"] = "cadence_not_due"
        _emit_ack(ack)
        return 0

    turns = build_capsule_turns(
        memory_entries=prior_entries,
        user_text=user,
        assistant_text=assistant,
        timestamp=stamp,
        trace_id=None,
    )

    vectorizer = build_cognitive_vectorizer(cfg)
    backend = normalize_cognitive_backend(
        getattr(cfg, "cognitive_memory_embedding_backend", "hashing")
    )
    capsule_store = MemoryCapsuleStore(memory_root / "capsules", config=cfg)
    try:
        result = capsule_store.write_capsule(
            turns=turns,
            session_id=working_session,
            source={
                "kind": "autowire",
                "tool": "autowire_turn",
                "version": CAPSULE_VERSION,
                "session_id": working_session,
            },
            vectorizer=vectorizer,
            vectorizer_backend=backend,
            created_at=stamp,
        )
        ack["capsule_written"] = True
        capsule_payload = result.get("capsule") if isinstance(result, dict) else None
        if isinstance(capsule_payload, dict):
            ack["capsule_id"] = capsule_payload.get("capsule_id")
        ack["capsule_path"] = result.get("path") if isinstance(result, dict) else None
    except Exception as exc:
        ack["fram_write"] = "error"
        ack["error"] = f"capsule_write_failed: {exc}"
        _emit_ack(ack)
        return 1

    # Append to working memory after capsule write to avoid duplicate entries in the capsule.
    _append_working(
        working_store, working_session, role="user", text=user, topic=topic, tags=tags
    )
    _append_working(
        working_store,
        working_session,
        role="assistant",
        text=assistant,
        topic=topic,
        tags=tags,
    )
    _emit_ack(ack)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
