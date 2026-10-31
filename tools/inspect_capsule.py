from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_ROLES = {"user", "assistant", "system", "tool", "memory"}


def _snippet(text: str, limit: int = 120) -> str:
    collapsed = " ".join(str(text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)] + "..."


def _preview(turns: List[Dict[str, Any]], head: int, tail: int) -> Dict[str, List[Dict[str, Any]]]:
    total = len(turns)
    head = max(0, int(head))
    tail = max(0, int(tail))
    head_items = turns[:head] if head > 0 else []
    tail_items = turns[-tail:] if tail > 0 else []
    if head > 0 and tail > 0 and (head + tail) > total:
        tail_items = []
    return {
        "head": [
            {
                "index": item.get("index"),
                "role": item.get("role"),
                "text": _snippet(item.get("text", "")),
            }
            for item in head_items
        ],
        "tail": [
            {
                "index": item.get("index"),
                "role": item.get("role"),
                "text": _snippet(item.get("text", "")),
            }
            for item in tail_items
        ],
    }


def _load_capsule(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Capsule not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in capsule: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Capsule payload is not a JSON object: {path}")
    return payload


def _summarize(payload: Dict[str, Any], *, head: int, tail: int) -> Dict[str, Any]:
    raw = payload.get("raw_transcript") or []
    trajectory = payload.get("trajectory") or []
    fractal = payload.get("fractal") or {}
    trace_stack = fractal.get("trace_stack") or []

    roles = [turn.get("role") for turn in raw]
    role_counts = Counter([role for role in roles if role is not None])
    unknown_roles = sorted({role for role in roles if role and role not in ALLOWED_ROLES})

    missing_embeddings = 0
    embed_dims = []
    embed_backends = []
    for entry in trajectory:
        embedding = entry.get("embedding")
        if not embedding:
            missing_embeddings += 1
            continue
        try:
            embed_dims.append(len(embedding))
        except Exception:
            missing_embeddings += 1
        backend = entry.get("embedding_backend")
        if backend:
            embed_backends.append(str(backend))

    embedding_dim = None
    if embed_dims:
        embedding_dim = embed_dims[0]
    elif fractal.get("embedding_dim") is not None:
        embedding_dim = fractal.get("embedding_dim")

    meta_with_entry_id = 0
    meta_with_last_seen = 0
    for turn in raw:
        meta = turn.get("meta") or {}
        if meta.get("entry_id"):
            meta_with_entry_id += 1
        if meta.get("last_seen"):
            meta_with_last_seen += 1

    return {
        "capsule_id": payload.get("capsule_id"),
        "capsule_version": payload.get("capsule_version"),
        "created_at": payload.get("created_at"),
        "session_id": payload.get("session_id"),
        "commit": payload.get("commit"),
        "source": payload.get("source"),
        "raw_turns": len(raw),
        "roles": roles,
        "role_counts": dict(role_counts),
        "unknown_roles": unknown_roles,
        "trajectory_count": len(trajectory),
        "embedding_dim": embedding_dim,
        "embedding_backends": sorted(set(embed_backends)),
        "missing_embeddings": missing_embeddings,
        "trace_stack_count": len(trace_stack),
        "trace_version": fractal.get("trace_version"),
        "remembering_definition_version": (payload.get("remembering_definition") or {}).get("version"),
        "alignment": {
            "raw_vs_trajectory": len(raw) == len(trajectory),
            "trajectory_vs_trace_stack": len(trajectory) == len(trace_stack),
        },
        "meta_counts": {
            "entry_id": meta_with_entry_id,
            "last_seen": meta_with_last_seen,
        },
        "preview": _preview(raw, head, tail),
    }


def _print_summary(summary: Dict[str, Any]) -> None:
    source = summary.get("source") or {}
    print(f"capsule_id: {summary.get('capsule_id')}")
    print(f"capsule_version: {summary.get('capsule_version')}")
    print(f"created_at: {summary.get('created_at')}")
    print(f"session_id: {summary.get('session_id')}")
    if summary.get("commit"):
        print(f"commit: {summary.get('commit')}")
    if isinstance(source, dict):
        print(
            "source: "
            f"kind={source.get('kind')} tool={source.get('tool')} version={source.get('version')}"
        )
    print(f"raw_turns: {summary.get('raw_turns')}")
    print(f"trajectory_count: {summary.get('trajectory_count')}")
    print(f"trace_stack_count: {summary.get('trace_stack_count')}")
    print(f"embedding_dim: {summary.get('embedding_dim')}")
    print(f"embedding_backends: {summary.get('embedding_backends')}")
    print(f"trace_version: {summary.get('trace_version')}")
    print(f"remembering_definition_version: {summary.get('remembering_definition_version')}")
    print("alignment:")
    alignment = summary.get("alignment") or {}
    print(f"  raw_vs_trajectory: {alignment.get('raw_vs_trajectory')}")
    print(f"  trajectory_vs_trace_stack: {alignment.get('trajectory_vs_trace_stack')}")
    meta_counts = summary.get("meta_counts") or {}
    print(
        "meta_counts: "
        f"entry_id={meta_counts.get('entry_id')} last_seen={meta_counts.get('last_seen')}"
    )
    if summary.get("missing_embeddings"):
        print(f"missing_embeddings: {summary.get('missing_embeddings')}")
    if summary.get("unknown_roles"):
        print(f"unknown_roles: {summary.get('unknown_roles')}")
    print(f"roles: {summary.get('roles')}")
    preview = summary.get("preview") or {}
    if preview.get("head"):
        print("preview_head:")
        for item in preview["head"]:
            print(f"  [{item.get('index')}] {item.get('role')}: {item.get('text')}")
    if preview.get("tail"):
        print("preview_tail:")
        for item in preview["tail"]:
            print(f"  [{item.get('index')}] {item.get('role')}: {item.get('text')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a Memory Capsule JSON file.")
    parser.add_argument("path", help="Path to a capsule JSON file.")
    parser.add_argument("--head", type=int, default=3, help="Number of leading turns to preview.")
    parser.add_argument("--tail", type=int, default=3, help="Number of trailing turns to preview.")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary instead of text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    payload = _load_capsule(path)
    summary = _summarize(payload, head=args.head, tail=args.tail)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
