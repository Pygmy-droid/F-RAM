
from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

try:
    import orjson
except Exception:  # pragma: no cover - orjson is optional
    orjson = None  # type: ignore[assignment]

import numpy as np

import mcp.types as mcp_types
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ResourceError
from mcp.server.lowlevel.server import request_ctx as _mcp_request_ctx
from mcp.server.session import InitializationState, ServerSession

try:
    from fram_serving.config import FRAMConfig as _RealFRAMConfig
except Exception:  # pragma: no cover - optional stub fallback
    _RealFRAMConfig = None

from fram_serving import observability
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.archive import ArchiveWriter
from fram_serving.memory import CognitiveMemoryStore, MemorySessionError, WorkingMemoryStore
from fram_serving.memory_capsule import MemoryCapsuleStore
from fram_serving.query_runner import QueryContext, run_query, _apply_phase_d_memory_bridge

if _RealFRAMConfig is not None:
    FRAMConfig = _RealFRAMConfig
else:  # pragma: no cover - fallback for missing config module
    try:
        from pydantic import BaseSettings
    except Exception:  # pragma: no cover - optional dependency
        BaseSettings = None  # type: ignore[assignment]

    if BaseSettings is not None:
        class FRAMConfig(BaseSettings):
            k0: int = 32
            rank_min: int = 6
            rank_max: int = 12
            hot_rank_cap: int = 8
            alpha1: float = 0.01
            alpha2: float = 0.003
            G: int = 16
            alpha_div: float = 0.2
            light_probe_m: int = 8
            headroom: float = 0.15
            eta: float = 0.4
            lambda_tok: float = 0.002
            lambda_rerank: float = 0.05
            theta_global: float = 0.7

            @classmethod
            def from_env(cls) -> "FRAMConfig":
                return cls()
    else:  # pragma: no cover - fallback without pydantic
        @dataclass(slots=True)
        class FRAMConfig:  # type: ignore[override]
            k0: int = 32
            rank_min: int = 6
            rank_max: int = 12
            hot_rank_cap: int = 8
            alpha1: float = 0.01
            alpha2: float = 0.003
            G: int = 16
            alpha_div: float = 0.2
            light_probe_m: int = 8
            headroom: float = 0.15
            eta: float = 0.4
            lambda_tok: float = 0.002
            lambda_rerank: float = 0.05
            theta_global: float = 0.7

            @classmethod
            def from_env(cls) -> "FRAMConfig":
                return cls()

            def model_dump(self) -> dict[str, Any]:
                return self.__dict__.copy()

DEFAULT_CFG = FRAMConfig()
DEFAULT_COG_BACKEND = getattr(DEFAULT_CFG, "cognitive_memory_embedding_backend", "hashing")
DEFAULT_COG_TOKEN_BUDGET = getattr(DEFAULT_CFG, "cognitive_memory_token_budget", 300)

try:
    from fram_serving.mcp_auth import token_verifier as _configured_token_verifier
except Exception:  # pragma: no cover - optional auth
    _configured_token_verifier = None

try:
    from fram_core.pipeline import (
        QueryOrchestrator as RealQueryOrchestrator,
        corpus_cache_to_dict,
        tokenize_text,
    )
except Exception:  # pragma: no cover - pipeline may be stubbed
    RealQueryOrchestrator = None  # type: ignore[assignment]
    corpus_cache_to_dict = None  # type: ignore[assignment]

    def tokenize_text(text: str) -> List[str]:  # type: ignore[override]
        return text.split()

ISO8601_FORMATS = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")

_ORIGINAL_MCP_RECEIVED_REQUEST = getattr(ServerSession, "_received_request", None)
if _ORIGINAL_MCP_RECEIVED_REQUEST is not None and not getattr(ServerSession, "_fram_relaxed_initialized", False):

    async def _fram_received_request_relaxed_initialized(self: ServerSession, responder) -> None:
        root = getattr(getattr(responder, "request", None), "root", None)

        if isinstance(root, mcp_types.InitializeRequest):
            await _ORIGINAL_MCP_RECEIVED_REQUEST(self, responder)
            if getattr(self, "_initialization_state", None) == InitializationState.Initializing:
                self._initialization_state = InitializationState.Initialized
            return

        if getattr(self, "_initialization_state", None) == InitializationState.Initializing:
            self._initialization_state = InitializationState.Initialized

        await _ORIGINAL_MCP_RECEIVED_REQUEST(self, responder)

    ServerSession._received_request = _fram_received_request_relaxed_initialized  # type: ignore[method-assign]
    ServerSession._fram_relaxed_initialized = True  # type: ignore[attr-defined]


UI_BASE_ENV = "FRAM_MEMORY_UI_BASE"


def _memory_ui_url(state: _MCPState, session_id: str | None = None) -> str:
    base = os.getenv(UI_BASE_ENV)
    if base:
        base = base.rstrip("/") or "/ui/memory"
        url = f"{base}/ui/memory" if not base.endswith("/ui/memory") else base
    else:
        url = "/ui/memory"
    if session_id:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}session={session_id}"
    return url


def _serialize_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f"Type is not JSON serializable: {type(value)!r}")


def _dumps(data: Any) -> str:
    if orjson is not None:
        return orjson.dumps(data, default=_serialize_default).decode("utf-8")
    return json.dumps(data, default=_serialize_default)


def _parse_iso8601(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        for fmt in ISO8601_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"Invalid ISO8601 datetime: {value}")


class TraceLogger:
    """In-memory trace store used by MCP tools."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._last_id: str | None = None

    def write(self, payload: dict[str, Any]) -> str:
        record = dict(payload)
        trace_id = record.setdefault("id", uuid.uuid4().hex)
        self._records[trace_id] = record
        self._last_id = trace_id
        return trace_id

    def read(self, trace_id: str) -> dict[str, Any] | None:
        return self._records.get(trace_id)

    def last_id(self) -> str | None:
        return self._last_id


class QueryOrchestrator:
    """Fallback orchestrator when real pipeline is unavailable."""

    def __init__(self, config: FRAMConfig, tracer: TraceLogger) -> None:
        self.config = config
        self.tracer = tracer
        self._impl = None
        if RealQueryOrchestrator is not None:
            try:
                self._impl = RealQueryOrchestrator(config=config, tracer=tracer)
            except Exception:
                self._impl = None

    def run(
        self,
        text: str,
        as_of: Optional[datetime],
        budget_reads: int,
        domain: str,
        task: str,
        cache_override: Any | None = None,
        memory_chunks: List[Dict[str, Any]] | None = None,
        *,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        if self._impl is not None and hasattr(self._impl, "run"):
            return self._impl.run(
                text,
                as_of,
                budget_reads,
                domain,
                task,
                cache_override=cache_override,
                memory_chunks=memory_chunks,
                version_id=version_id,
            )

        answer = f"Stub answer for: {text}"
        trace_payload = {
            "query": text,
            "as_of": as_of.isoformat() if as_of else None,
            "budget_reads": budget_reads,
            "domain": domain,
            "task": task,
            "answer": answer,
            "citations": [],
            "coverage": {},
        }
        trace_id = self.tracer.write(trace_payload)
        trace_payload["trace_id"] = trace_id
        return {
            "trace_id": trace_id,
            "answer": answer,
            "citations": [],
            "coverage": {},
        }

    def ensure_corpus(self) -> Any | None:
        if self._impl is not None and hasattr(self._impl, "ensure_corpus"):
            try:
                return self._impl.ensure_corpus()
            except Exception:
                return None
        return None

    def get_embeddings_for_shortlist(self, query_text: str, shortlist: List[Dict[str, Any]]):
        if self._impl is not None and hasattr(self._impl, "get_embeddings_for_shortlist"):
            try:
                return self._impl.get_embeddings_for_shortlist(query_text, shortlist)
            except Exception:
                return ([], [])
        return ([], [])


@dataclass(slots=True)
class _MCPState:
    config: FRAMConfig
    tracer: TraceLogger
    orchestrator: QueryOrchestrator
    memory_store: WorkingMemoryStore
    cognitive_store: CognitiveMemoryStore
    capsule_store: MemoryCapsuleStore
    cognitive_vectorizer: Any | None
    cognitive_vectorizer_backend: str | None
    observability_dir: Path


_STATE: _MCPState | None = None
_DOC_CACHE: Dict[str, Any] | None = None
_DOC_CACHE_ROOT: Path | None = None
_NEGATIVE_COOLDOWNS: Dict[str, datetime] = {}


def _build_state(config: FRAMConfig | None = None) -> _MCPState:
    global _DOC_CACHE, _DOC_CACHE_ROOT, _NEGATIVE_COOLDOWNS
    config = config or FRAMConfig.from_env()
    _DOC_CACHE = None
    _DOC_CACHE_ROOT = None
    _NEGATIVE_COOLDOWNS = {}
    tracer = TraceLogger()
    orchestrator = QueryOrchestrator(config=config, tracer=tracer)

    root = Path(config.STORAGE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    for sub in config.STORAGE_SUBFOLDERS.values():
        (root / sub).mkdir(parents=True, exist_ok=True)

    memory_root = root / config.STORAGE_SUBFOLDERS.get("memory", "memory")
    observability_dir = root / config.STORAGE_SUBFOLDERS.get("observability", "observability")
    memory_store = WorkingMemoryStore(
        memory_root,
        dedupe_window_seconds=getattr(config, "working_memory_dedupe_window_sec", 0),
    )
    cognitive_store = CognitiveMemoryStore(memory_root / "cognitive", config=config)
    capsule_store = MemoryCapsuleStore(memory_root / "capsules", config=config)
    try:
        backend = normalize_cognitive_backend(
            getattr(config, "cognitive_memory_embedding_backend", "hashing")
        )
    except Exception:
        backend = "hashing"
    vectorizer: Any | None = build_cognitive_vectorizer(config)

    return _MCPState(
        config=config,
        tracer=tracer,
        orchestrator=orchestrator,
        memory_store=memory_store,
        cognitive_store=cognitive_store,
        capsule_store=capsule_store,
        cognitive_vectorizer=vectorizer,
        cognitive_vectorizer_backend=backend,
        observability_dir=observability_dir,
    )


@asynccontextmanager
async def lifespan(_: FastMCP[_MCPState]) -> _MCPState:
    global _STATE
    _STATE = _build_state()
    try:
        yield _STATE
    finally:
        _STATE = None


def _get_state() -> _MCPState:
    try:
        ctx = _mcp_request_ctx.get()
    except LookupError:
        ctx = None
    if ctx is not None:
        return ctx.lifespan_context
    if _STATE is None:
        raise RuntimeError("MCP server state not initialized")
    return _STATE


_issuer_url = os.getenv("MCP_AUTH_ISSUER", "https://chat.openai.com")
_resource_server_url = os.getenv("MCP_RESOURCE_SERVER_URL", "https://chat.openai.com/mcp")
_expected_token = os.getenv("MCP_BEARER", "").strip()

_auth_settings: AuthSettings | None = None
_token_verifier = _configured_token_verifier
if _token_verifier is not None and _expected_token:
    _auth_settings = AuthSettings(
        issuer_url=_issuer_url,
        resource_server_url=_resource_server_url,
    )

mcp = FastMCP(
    "FRAM v2.2",
    lifespan=lifespan,
    auth=_auth_settings,
    token_verifier=_token_verifier if _auth_settings is not None else None,
    # This server is mounted under `/mcp` by `fram_serving.app`; expose the StreamableHTTP
    # transport at the sub-app root so the external endpoint remains `/mcp`.
    streamable_http_path="/",
)

if _auth_settings is not None and mcp.settings.auth is not None:
    if _token_verifier is not None and os.getenv("MCP_BEARER"):
        object.__setattr__(mcp.settings.auth, "token_verifier", _token_verifier)


def _build_trace_uri(trace_id: str | None) -> str:
    return f"fram://trace/{trace_id}" if trace_id else ""


def _trace_dir(config: FRAMConfig) -> Path:
    subfolders = getattr(config, "STORAGE_SUBFOLDERS", {}) or {}
    return Path(config.STORAGE_ROOT) / subfolders.get("traces", "traces")


def _ensure_doc_cache(state: _MCPState) -> Dict[str, Any]:
    global _DOC_CACHE, _DOC_CACHE_ROOT
    root = Path(state.config.STORAGE_ROOT).resolve()
    if _DOC_CACHE is not None and _DOC_CACHE_ROOT == root:
        return _DOC_CACHE
    corpus = None
    if hasattr(state.orchestrator, "ensure_corpus"):
        corpus = state.orchestrator.ensure_corpus()
    if corpus is not None and corpus_cache_to_dict is not None:
        _DOC_CACHE = corpus_cache_to_dict(corpus)
    else:
        _DOC_CACHE = {}
    _DOC_CACHE_ROOT = root
    return _DOC_CACHE


def _get_memory_vectorizer(state: _MCPState) -> Any | None:
    try:
        backend = normalize_cognitive_backend(
            getattr(state.config, "cognitive_memory_embedding_backend", "hashing")
        )
    except Exception:
        backend = "hashing"
    if backend != state.cognitive_vectorizer_backend:
        state.cognitive_vectorizer = build_cognitive_vectorizer(state.config)
        state.cognitive_vectorizer_backend = backend
    return state.cognitive_vectorizer


def _encode_cognitive_text(state: _MCPState, text: str) -> tuple[list[float] | None, str | None]:
    vectorizer = _get_memory_vectorizer(state)
    backend = normalize_cognitive_backend(
        getattr(state.config, "cognitive_memory_embedding_backend", "hashing")
    )
    if vectorizer is None:
        return None, backend
    try:
        matrix = vectorizer.transform([text])
    except Exception:
        return None, backend
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()
    else:
        arr = np.asarray(matrix)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    vec = arr.astype(float, copy=False).ravel()
    return vec.tolist(), backend


def _cooldown_remaining(doc_id: str, reference: datetime, window: timedelta) -> float | None:
    ts = _NEGATIVE_COOLDOWNS.get(doc_id)
    if ts is None:
        return None
    remaining = (window - (reference - ts)).total_seconds()
    if remaining > 0:
        return remaining
    return None


def _log_memory_event(state: _MCPState, session_id: str, event: str, **fields: Any) -> None:
    if not session_id:
        return
    payload = {"session_id": session_id, "event": event}
    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    observability.log_memory_event(state.observability_dir, payload)


def _prepare_memory_for_query(state: _MCPState, session_id: str):
    info = state.memory_store.session_info(session_id)
    status = str(info.get("status", WorkingMemoryStore.STATUS_ACTIVE))
    entries = state.memory_store.list(session_id)
    available = len(entries)
    chunks = None
    used = 0
    if status == WorkingMemoryStore.STATUS_ACTIVE:
        if entries:
            chunks = state.memory_store.session_chunks(session_id, entries)
            used = len(chunks)
        else:
            chunks = []
    trace = {
        "session": session_id,
        "status": status,
        "available": available,
        "used": used,
    }
    return chunks, trace


@mcp.tool(
    name="fram.query", description="Submit a FRAM retrieval query; writes traces and archives",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def fram_query(
    ctx: Context[ServerSession, _MCPState, Any],
    query: str,
    as_of: str | None = None,
    version_id: str | None = None,
    budget_reads: int = 2000,
    domain: str = "general",
    task: str = "qa",
    memory_session: str | None = None,
    persist_cognitive: bool = False,
) -> dict[str, Any]:
    state = _get_state()
    if not query:
        raise ValueError("query must be provided")

    cooldown_window = timedelta(minutes=max(1, int(getattr(state.config, "negative_cue_cooldown_minutes", 10))))
    trace_dir = _trace_dir(state.config)

    req = SimpleNamespace(
        text=query,
        as_of=as_of,
        version_id=version_id,
        budget_reads=budget_reads,
        memory_session=memory_session,
        domain=domain,
        task=task,
    )
    persist_allowed = bool(getattr(state.config, "mcp_cognitive_write_enabled", False))
    persist_enabled = bool(persist_cognitive) and persist_allowed
    run_ctx = QueryContext(
        cfg=state.config,
        orchestrator=state.orchestrator,
        memory_store=state.memory_store,
        cognitive_store=state.cognitive_store,
        capsule_store=state.capsule_store,
        get_memory_vectorizer=lambda: _get_memory_vectorizer(state),
        encode_cognitive_text=lambda text: _encode_cognitive_text(state, text),
        apply_phase_d_memory_bridge=lambda text, candidates, debug: _apply_phase_d_memory_bridge(
            state.config, state.orchestrator, text, candidates, debug
        ),
        cooldown_active=lambda doc_id, reference: _cooldown_remaining(doc_id, reference, cooldown_window) is not None,
        register_cooldown=lambda doc_id, timestamp: _NEGATIVE_COOLDOWNS.__setitem__(doc_id, timestamp),
        cooldown_window=cooldown_window,
        resolve_time_sensitivity=lambda task_value, domain_value: str(
            (
                (getattr(state.config, "time_sensitivity_task", {}) or {}).get(task_value)
                or (getattr(state.config, "time_sensitivity_domain", {}) or {}).get(domain_value)
                or "medium"
            )
        ).lower(),
        ensure_doc_cache=lambda: _ensure_doc_cache(state),
        trace_writer=observability.TraceLogWriter(trace_dir),
        observability_dir=state.observability_dir,
        trace_dir=trace_dir,
        store_prob=lambda *args, **kwargs: None,
        log_memory_event=lambda session_id, event, **fields: _log_memory_event(state, session_id, event, **fields),
        archive_writer=ArchiveWriter(state.config.STORAGE_ROOT / "archive"),
        archive_kind="mcp_query",
        cognitive_write_enabled=persist_enabled,
    )

    result = run_query(req, run_ctx)
    trace_id = result.get("id")
    trace_uri = _build_trace_uri(trace_id)
    if trace_uri:
        await ctx.info(f"trace available at {trace_uri}")
    trace_payload = result.get("trace") if isinstance(result, dict) else None
    coverage = {}
    memory_trace = None
    if isinstance(trace_payload, dict):
        coverage = trace_payload.get("coverage") or {}
        memory_trace = trace_payload.get("memory")
    response = {
        "answer": result.get("answer"),
        "citations": result.get("citations", []),
        "coverage": coverage,
        "trace_uri": trace_uri,
        "cognitive_episode_write_ok": result.get("cognitive_episode_write_ok", True),
    }
    if memory_trace is not None:
        response["memory"] = memory_trace
        response["memory_ui"] = _memory_ui_url(state, memory_trace.get("session"))
    return response



@mcp.tool(
    name="fram.get_trace_uri", description="Return the most recent trace URI",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def fram_get_trace_uri(ctx: Context[ServerSession, _MCPState, Any]) -> str:
    state = _get_state()
    trace_id = state.tracer.last_id()
    uri = _build_trace_uri(trace_id)
    if uri:
        await ctx.debug(f"last trace uri: {uri}")
    return uri


@mcp.tool(
    name="fram.memory_list", description="List working-memory sessions; initializes missing legacy session metadata",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_list(ctx: Context[ServerSession, _MCPState, Any]) -> List[dict[str, Any]]:
    state = _get_state()
    sessions: List[dict[str, Any]] = []
    for summary in state.memory_store.session_summaries():
        item = dict(summary)
        item["ui_url"] = _memory_ui_url(state, item.get("id"))
        sessions.append(item)
    await ctx.debug(f"memory sessions listed: {len(sessions)}")
    return sessions


@mcp.tool(
    name="fram.memory_bootstrap",
    description="Search cognitive memory or summarise recent activity; search writes telemetry.",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_bootstrap(
    ctx: Context[ServerSession, _MCPState, Any],
    query: Optional[str] = None,
    k: int = 5,
    domain: Optional[str] = None,
    task: Optional[str] = None,
    window: int = 20,
) -> dict[str, Any]:
    state = _get_state()
    log_path = state.observability_dir / "memory_cognitive.jsonl"
    filters: Dict[str, Any] = {}
    domain_norm = domain.strip().lower() if isinstance(domain, str) and domain.strip() else None
    task_norm = task.strip().lower() if isinstance(task, str) and task.strip() else None
    if domain_norm:
        filters["domain"] = domain_norm
    if task_norm:
        filters["task"] = task_norm

    if query and query.strip():
        k = max(1, int(k))
        vectorizer = state.cognitive_vectorizer
        results = state.cognitive_store.search(
            query.strip(),
            k=k,
            filters=filters or None,
            vectorizer=vectorizer,
        )
        selected_payload: List[Dict[str, Any]] = []
        for item in results:
            kind = str(item.get("kind") or "episode")
            if kind == "episode":
                text = f"Q: {item.get('query', '')}\nA: {item.get('answer', '')}"
            else:
                text = str(item.get("text") or "")
            tokens = len(tokenize_text(text))
            selected_payload.append(
                {
                    "id": item.get("id") or item.get("trace_id") or item.get("doc_id"),
                    "kind": kind,
                    "score": item.get("_score"),
                    "tokens": tokens,
                }
            )
        event = {
            "mode": "search",
            "backend": getattr(state.config, "cognitive_memory_embedding_backend", DEFAULT_COG_BACKEND),
            "k_requested": k,
            "results": len(results),
            "token_budget": getattr(state.config, "cognitive_memory_token_budget", DEFAULT_COG_TOKEN_BUDGET),
            "selected_count": len(selected_payload),
            "selected": selected_payload,
            "domain": domain_norm,
            "task": task_norm,
            "query_preview": query.strip()[:200],
        }
        observability.log_cognitive_memory_event(
            state.observability_dir,
            {**event, "source": "mcp"},
        )
        await ctx.info(f"cognitive memory search produced {len(results)} results")
        return {
            "mode": "search",
            "query": query,
            "results": results,
            "event": event,
            "filters": filters,
            "log_path": str(log_path),
        }

    window = max(1, int(window))
    summary = state.cognitive_store.summarize(window=window)
    summary.update(
        {
            "mode": "summary",
            "window": window,
            "log_path": str(log_path),
            "source": "cognitive",
        }
    )
    await ctx.debug("cognitive memory summary generated")
    return summary


@mcp.tool(
    name="fram.memory_get", description="Fetch a working-memory session; initializes metadata when missing",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_get(
    ctx: Context[ServerSession, _MCPState, Any], session_id: str, include_entries: bool = False
) -> dict[str, Any]:
    state = _get_state()
    info = state.memory_store.session_info(session_id)
    entries = state.memory_store.list(session_id) if include_entries else None
    payload = {"session": info, "ui_url": _memory_ui_url(state, session_id)}
    if entries is not None:
        payload["entries"] = entries
    await ctx.debug(f"memory session fetched: {session_id}")
    return payload


@mcp.tool(
    name="fram.memory_create", description="Create or upsert a working-memory session",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_create(
    ctx: Context[ServerSession, _MCPState, Any], session_id: str | None = None, metadata: Optional[Dict[str, Any]] = None
) -> dict[str, Any]:
    state = _get_state()
    info = state.memory_store.create(session_id, metadata=metadata)
    created = bool(info.pop("created", False))
    session = info.get("id")
    if session:
        _log_memory_event(
            state,
            session,
            "create",
            status=info.get("status"),
            entry_count=info.get("entry_count"),
            created=created,
        )
    await ctx.info(f"memory session ready: {session}")
    return {"session": info, "created": created, "ui_url": _memory_ui_url(state, session)}


@mcp.tool(
    name="fram.memory_control", description="Update a session lifecycle state",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_control(
    ctx: Context[ServerSession, _MCPState, Any], session_id: str, action: str
) -> dict[str, Any]:
    state = _get_state()
    action_norm = action.lower()
    if action_norm == "continue":
        action_norm = "resume"
    if action_norm == "resume":
        info = state.memory_store.set_status(session_id, WorkingMemoryStore.STATUS_ACTIVE)
    elif action_norm == "pause":
        info = state.memory_store.set_status(session_id, WorkingMemoryStore.STATUS_PAUSED)
    elif action_norm == "end":
        info = state.memory_store.set_status(session_id, WorkingMemoryStore.STATUS_ENDED)
    else:
        raise ValueError("invalid action")
    _log_memory_event(
        state,
        session_id,
        "control",
        action=action_norm,
        status=info.get("status"),
        entry_count=info.get("entry_count"),
    )
    await ctx.info(f"memory session {session_id} -> {action_norm}")
    return {"session": info, "action": action_norm, "ui_url": _memory_ui_url(state, session_id)}


@mcp.tool(
    name="fram.memory_append", description="Append text to a working-memory session",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_append(
    ctx: Context[ServerSession, _MCPState, Any], session_id: str, text: str, metadata: Optional[Dict[str, Any]] = None
) -> dict[str, Any]:
    state = _get_state()
    if not text or not text.strip():
        raise ValueError("text must be provided")
    try:
        entry = state.memory_store.append(session_id, text.strip(), metadata)
    except MemorySessionError as exc:
        raise ValueError(str(exc)) from exc
    info = state.memory_store.session_info(session_id)
    _log_memory_event(
        state,
        session_id,
        "append",
        status=info.get("status"),
        entry_count=info.get("entry_count"),
        entry_id=entry.get("id"),
        deduped=entry.get("deduped"),
    )
    await ctx.info(f"memory session {session_id} appended")
    entry_with_url = dict(entry)
    entry_with_url["ui_url"] = _memory_ui_url(state, session_id)
    return entry_with_url


@mcp.tool(
    name="fram.memory_clear", description="Remove all entries from a session",
    annotations=mcp_types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
)
async def fram_memory_clear(ctx: Context[ServerSession, _MCPState, Any], session_id: str) -> dict[str, Any]:
    state = _get_state()
    state.memory_store.ensure_session(session_id)
    state.memory_store.clear(session_id)
    info = state.memory_store.session_info(session_id)
    _log_memory_event(
        state,
        session_id,
        "clear",
        status=info.get("status"),
        entry_count=info.get("entry_count"),
    )
    await ctx.info(f"memory session {session_id} cleared")
    return {"session": info, "cleared": True, "ui_url": _memory_ui_url(state, session_id)}


@mcp.resource("fram://trace/{trace_id}", name="FRAM Trace", description="Return stored FRAM decision trace", mime_type="application/json")
async def read_trace(trace_id: str) -> str:
    state = _get_state()
    record = state.tracer.read(trace_id)
    if record is None:
        raise ResourceError(f"Trace not found: {trace_id}")
    return _dumps(record)


@mcp.resource("fram://config", name="FRAM Config", description="Return the active FRAM configuration", mime_type="application/json")
async def read_config() -> str:
    state = _get_state()
    config = state.config
    payload = config.model_dump() if hasattr(config, "model_dump") else vars(config)
    # Match REST /config: observability must not export credentials. Copy first
    # because the fallback uses vars(config), which is the object's live state.
    public_payload = {key: value for key, value in payload.items() if key != "api_key"}
    return _dumps(public_payload)
