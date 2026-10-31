from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_core.pipeline import (
    _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer,
)
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Hydrate FRAM cognitive memory for session bootstraps. "
            "Attempts to call the running server first, then falls back to reading the JSONL store directly."
        )
    )
    parser.add_argument(
        "--query",
        help="Search text for memory recall. If omitted, prints a recent-summary window instead.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of search results to return (default: %(default)s).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=20,
        help="Number of recent entries to include when --query is not provided (default: %(default)s).",
    )
    parser.add_argument(
        "--domain",
        help="Optional domain filter for search results.",
    )
    parser.add_argument(
        "--task",
        help="Optional task filter for search results.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"FRAM server base URL for REST calls (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--storage-root",
        help="Override storage root when falling back to local JSONL files.",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "server", "files"],
        default="auto",
        help="Where to read data from (default: auto).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="HTTP timeout in seconds when contacting the server (default: %(default)s).",
    )
    return parser.parse_args()


def _attempt_server_fetch(
    base_url: str,
    timeout: float,
    query: Optional[str],
    limit: int,
    window: int,
    domain: Optional[str],
    task: Optional[str],
) -> Optional[Dict[str, Any]]:
    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            if query:
                params = {"query": query, "k": limit}
                if domain:
                    params["domain"] = domain
                if task:
                    params["task"] = task
                resp = client.get("/memory/search", params=params)
                resp.raise_for_status()
                payload = resp.json()
                payload["source"] = "server"
                payload["base_url"] = base_url
                return payload
            resp = client.get("/observability/memory/summary", params={"window": window})
            resp.raise_for_status()
            payload = resp.json()
            payload["source"] = "server"
            payload["base_url"] = base_url
            return payload
    except Exception:
        return None


def _make_memory_vectorizer(cfg: FRAMConfig) -> Any | None:
    try:
        backend = str(getattr(cfg, "cognitive_memory_embedding_backend", "hashing")).lower()
    except Exception:
        backend = "hashing"
    if backend == "hashing":
        return _pipeline_make_hashing_vectorizer(cfg)
    return None


def _resolve_storage_root(cfg: FRAMConfig, override: Optional[str]) -> Path:
    base = Path(override).expanduser().resolve() if override else cfg.STORAGE_ROOT
    root = base / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    return root.resolve()


def _fetch_from_files(
    cfg: FRAMConfig,
    storage_root: Path,
    query: Optional[str],
    limit: int,
    window: int,
    domain: Optional[str],
    task: Optional[str],
) -> Dict[str, Any]:
    store = CognitiveMemoryStore(storage_root, config=cfg)
    vectorizer = _make_memory_vectorizer(cfg)
    if query:
        filters: Dict[str, Any] = {}
        if domain:
            filters["domain"] = domain
        if task:
            filters["task"] = task
        results = store.search(
            query,
            k=limit,
            filters=filters or None,
            vectorizer=vectorizer,
        )
        return {
            "source": "files",
            "storage_root": str(storage_root),
            "results": results,
            "query": query,
        }
    summary = store.summarize(window=window)
    summary["source"] = "files"
    summary["storage_root"] = str(storage_root)
    summary["window"] = window
    return summary


def _format_score(score: Any) -> str:
    try:
        return f"{float(score):.3f}"
    except Exception:
        return "?"


def _emit_text(payload: Dict[str, Any], query: Optional[str]) -> None:
    lines: List[str] = []
    header = "[FRAM Cognitive Memory]"
    if payload.get("source") == "server":
        lines.append(f"{header} via server {payload.get('base_url')}")
    elif payload.get("source") == "files":
        lines.append(f"{header} via files {payload.get('storage_root')}")
    else:
        lines.append(header)

    if query:
        results: Iterable[Dict[str, Any]] = payload.get("results", [])
        if not results:
            lines.append("No matching episodes/beliefs were found.")
        else:
            lines.append(f"Top {len(results)} results for query: {query!r}")
            for idx, item in enumerate(results, 1):
                kind = item.get("kind") or "episode"
                rid = item.get("id") or item.get("doc_id") or "unknown"
                score = _format_score(item.get("_score"))
                entry_lines = [
                    f"{idx}. [{kind}] score={score} id={rid}",
                ]
                domain = item.get("domain")
                task = item.get("task")
                if domain or task:
                    entry_lines.append(f"   meta: domain={domain or '-'} task={task or '-'}")
                if kind == "episode":
                    q = (item.get("query") or "").strip()
                    a = (item.get("answer") or "").strip()
                    if q:
                        entry_lines.append(f"   Q: {q}")
                    if a:
                        entry_lines.append(f"   A: {a}")
                else:
                    text = (item.get("text") or "").strip()
                    if text:
                        entry_lines.append(f"   {text}")
                citations = item.get("citations") or []
                if citations:
                    entry_lines.append(f"   citations: {', '.join(map(str, citations))}")
                lines.extend(entry_lines)
    else:
        counts = payload.get("counts") or {}
        lines.append(
            "Counts: "
            + ", ".join(f"{key}={counts.get(key, 0)}" for key in ("episodes", "beliefs", "links"))
        )
        recent = payload.get("recent") or {}
        if recent:
            episodes = recent.get("episodes") or []
            beliefs = recent.get("beliefs") or []
            if episodes:
                lines.append("")
                lines.append(f"Recent episodes (last {len(episodes)}):")
                for ep in episodes:
                    q = (ep.get("query") or "").strip()
                    a = (ep.get("answer") or "").strip()
                    ts = ep.get("time") or "unknown"
                    line = f"- {ts} :: {q}"
                    if a:
                        line += f" | {a}"
                    lines.append(line)
            if beliefs:
                lines.append("")
                lines.append(f"Recent beliefs (last {len(beliefs)}):")
                for bl in beliefs:
                    ts = bl.get("time") or "unknown"
                    text = (bl.get("text") or "").strip()
                    confidence = bl.get("confidence")
                    if confidence is not None:
                        lines.append(f"- {ts} :: {text} (confidence={confidence})")
                    else:
                        lines.append(f"- {ts} :: {text}")
    return lines


def _build_text_lines(payload: Dict[str, Any], query: Optional[str]) -> List[str]:
    lines: List[str] = []
    header = "[FRAM Cognitive Memory]"
    if payload.get("source") == "server":
        lines.append(f"{header} via server {payload.get('base_url')}")
    elif payload.get("source") == "files":
        lines.append(f"{header} via files {payload.get('storage_root')}")
    else:
        lines.append(header)

    if query:
        results: Iterable[Dict[str, Any]] = payload.get("results", [])
        if not results:
            lines.append("No matching episodes/beliefs were found.")
        else:
            lines.append(f"Top {len(results)} results for query: {query!r}")
            for idx, item in enumerate(results, 1):
                kind = item.get("kind") or "episode"
                rid = item.get("id") or item.get("doc_id") or "unknown"
                score = _format_score(item.get("_score"))
                entry_lines = [
                    f"{idx}. [{kind}] score={score} id={rid}",
                ]
                domain = item.get("domain")
                task = item.get("task")
                if domain or task:
                    entry_lines.append(f"   meta: domain={domain or '-'} task={task or '-'}")
                if kind == "episode":
                    q = (item.get("query") or "").strip()
                    a = (item.get("answer") or "").strip()
                    if q:
                        entry_lines.append(f"   Q: {q}")
                    if a:
                        entry_lines.append(f"   A: {a}")
                else:
                    text = (item.get("text") or "").strip()
                    if text:
                        entry_lines.append(f"   {text}")
                citations = item.get("citations") or []
                if citations:
                    entry_lines.append(f"   citations: {', '.join(map(str, citations))}")
                lines.extend(entry_lines)
    else:
        counts = payload.get("counts") or {}
        lines.append(
            "Counts: "
            + ", ".join(f"{key}={counts.get(key, 0)}" for key in ("episodes", "beliefs", "links"))
        )
        recent = payload.get("recent") or {}
        if recent:
            episodes = recent.get("episodes") or []
            beliefs = recent.get("beliefs") or []
            if episodes:
                lines.append("")
                lines.append(f"Recent episodes (last {len(episodes)}):")
                for ep in episodes:
                    q = (ep.get("query") or "").strip()
                    a = (ep.get("answer") or "").strip()
                    ts = ep.get("time") or "unknown"
                    line = f"- {ts} :: {q}"
                    if a:
                        line += f" | {a}"
                    lines.append(line)
            if beliefs:
                lines.append("")
                lines.append(f"Recent beliefs (last {len(beliefs)}):")
                for bl in beliefs:
                    ts = bl.get("time") or "unknown"
                    text = (bl.get("text") or "").strip()
                    confidence = bl.get("confidence")
                    if confidence is not None:
                        lines.append(f"- {ts} :: {text} (confidence={confidence})")
                    else:
                        lines.append(f"- {ts} :: {text}")
    return lines


def format_text(payload: Dict[str, Any], query: Optional[str]) -> str:
    return "\n".join(_build_text_lines(payload, query))


def _emit_text(payload: Dict[str, Any], query: Optional[str]) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    for line in _build_text_lines(payload, query):
        safe_line = line.encode(encoding, errors="replace").decode(encoding)
        print(safe_line)


def load_payload(
    *,
    query: Optional[str] = None,
    limit: int = 5,
    window: int = 20,
    domain: Optional[str] = None,
    task: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    storage_root: Optional[str] = None,
    source: str = "auto",
    timeout: float = 3.0,
) -> Tuple[Dict[str, Any], str]:
    cfg = FRAMConfig.from_env()
    storage_override: Optional[Path] = None
    if storage_root:
        storage_override = Path(storage_root).expanduser().resolve()
        cfg = cfg.model_copy(update={"STORAGE_ROOT": storage_override})

    payload: Optional[Dict[str, Any]] = None
    source = source.lower()
    if source not in {"auto", "server", "files"}:
        raise ValueError("source must be one of: auto, server, files")
    sources_to_try: List[str]
    if source == "auto":
        sources_to_try = ["server", "files"]
    elif source == "server":
        sources_to_try = ["server"]
    else:
        sources_to_try = ["files"]

    for mode in sources_to_try:
        if mode == "server":
            payload = _attempt_server_fetch(
                base_url=base_url,
                timeout=timeout,
                query=query,
                limit=max(1, int(limit)),
                window=max(1, int(window)),
                domain=domain,
                task=task,
            )
        else:
            storage_root_path = _resolve_storage_root(cfg, storage_root)
            payload = _fetch_from_files(
                cfg=cfg,
                storage_root=storage_root_path,
                query=query,
                limit=max(1, int(limit)),
                window=max(1, int(window)),
                domain=domain,
                task=task,
            )
        if payload is not None:
            return payload, mode

    raise RuntimeError("Unable to load cognitive memory (server unreachable and no JSONL files found).")


def main() -> int:
    args = parse_args()
    try:
        payload, _mode = load_payload(
            query=args.query,
            limit=args.limit,
            window=args.window,
            domain=args.domain,
            task=args.task,
            base_url=args.base_url,
            storage_root=args.storage_root,
            source=args.source,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        _emit_text(payload, args.query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
