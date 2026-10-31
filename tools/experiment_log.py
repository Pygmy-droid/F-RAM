from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

# Allow importing the helper even if 'tools' isn't a package
THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
REPO_ROOT = THIS_FILE.parents[1]
for p in (str(TOOLS_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fram_serving.config import FRAMConfig
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.memory_capsule import CAPSULE_VERSION, MemoryCapsuleStore, build_capsule_turns


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


def _prompt(label: str, *, optional: bool = True) -> str:
    suffix = " (optional)" if optional else ""
    value = input(f"{label}{suffix}: ").strip()
    if not value and not optional:
        return _prompt(label, optional=optional)
    return value


def _encode_text(text: str, vectorizer: Any | None) -> Sequence[float] | None:
    if vectorizer is None or not text:
        return None
    try:
        matrix = vectorizer.transform([text])
    except Exception:
        return None
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()
    else:
        arr = np.asarray(matrix)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    vec = arr.astype(float, copy=False).ravel()
    return vec.tolist()


def _format_block(title: str, value: str) -> str:
    if not value:
        return ""
    return f"{title}: {value}"


def log_experiment(
    *,
    title: str,
    hypothesis: str = "",
    method: str = "",
    result: str = "",
    decision: str = "",
    metrics: str = "",
    notes: str = "",
    tags: Optional[str] = None,
    topic: Optional[str] = None,
    session_id: Optional[str] = None,
    write_capsule: bool = False,
    working_session_id: Optional[str] = None,
) -> dict:
    cfg = FRAMConfig.from_env()
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if override_root:
        cfg = cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})

    memory_root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    store = CognitiveMemoryStore(memory_root / "cognitive", config=cfg)

    run_id = uuid.uuid4().hex
    stamp = datetime.now(timezone.utc).isoformat()
    tag_list = _parse_tags(tags)
    if "experiment" not in tag_list:
        tag_list.append("experiment")
    if decision and "decision" not in tag_list:
        tag_list.append("decision")

    blocks = [
        _format_block("Experiment", title),
        _format_block("Hypothesis", hypothesis),
        _format_block("Method", method),
        _format_block("Result", result),
        _format_block("Decision", decision),
        _format_block("Metrics", metrics),
        _format_block("Notes", notes),
        _format_block("Run ID", run_id),
        _format_block("Timestamp", stamp),
    ]
    text = "\n".join([block for block in blocks if block])

    vectorizer = build_cognitive_vectorizer(cfg)
    embedding = _encode_text(text, vectorizer)
    backend = normalize_cognitive_backend(
        getattr(cfg, "cognitive_memory_embedding_backend", "hashing")
    )

    meta = {
        "kind": "experiment",
        "title": title,
        "run_id": run_id,
        "tags": tag_list,
    }
    if topic:
        meta["topic"] = topic
    if decision:
        meta["decision"] = decision

    session = session_id or os.getenv("COGMEM_SESSION_ID") or "default"
    record = store.append_belief(
        text=text,
        session_id=session,
        role="assistant",
        metadata=meta,
        embedding=embedding,
        embedding_backend=backend,
    )
    if write_capsule:
        session_ref = working_session_id or session
        working_store = WorkingMemoryStore(memory_root)
        prior_entries = working_store.list(session_ref)
        turns = build_capsule_turns(
            memory_entries=prior_entries,
            user_text="Experiment log",
            assistant_text=text,
            timestamp=stamp,
            trace_id=None,
        )
        capsule_store = MemoryCapsuleStore(memory_root / "capsules", config=cfg)
        capsule_store.write_capsule(
            turns=turns,
            session_id=session_ref,
            source={
                "kind": "experiment",
                "tool": "experiment_log",
                "version": CAPSULE_VERSION,
                "session_id": session_ref,
                "run_id": run_id,
            },
            vectorizer=vectorizer,
            vectorizer_backend=backend,
            created_at=stamp,
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Log a structured experiment into cognitive memory.")
    parser.add_argument("--title", help="Short experiment title")
    parser.add_argument("--hypothesis", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--metrics", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--topic", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--json", action="store_true", help="Print the stored record as JSON.")
    parser.add_argument("--write-capsule", action="store_true", help="Write a capsule snapshot for this experiment.")
    parser.add_argument("--working-session-id", default=None, help="Working-memory session id for capsule context.")
    parser.add_argument("--interactive", action="store_true", help="Prompt for fields.")
    args = parser.parse_args()

    title = args.title
    if args.interactive or not title:
        title = _prompt("Title", optional=False)
        hypothesis = _prompt("Hypothesis")
        method = _prompt("Method")
        result = _prompt("Result")
        decision = _prompt("Decision")
        metrics = _prompt("Metrics")
        notes = _prompt("Notes")
        tags = _prompt("Tags (comma or space separated)")
        topic = _prompt("Topic")
    else:
        hypothesis = args.hypothesis
        method = args.method
        result = args.result
        decision = args.decision
        metrics = args.metrics
        notes = args.notes
        tags = args.tags
        topic = args.topic

    record = log_experiment(
        title=title,
        hypothesis=hypothesis,
        method=method,
        result=result,
        decision=decision,
        metrics=metrics,
        notes=notes,
        tags=tags,
        topic=topic or None,
        session_id=args.session_id,
        write_capsule=bool(args.write_capsule),
        working_session_id=args.working_session_id,
    )

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
