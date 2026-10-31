"""Evaluate the real run_query cognitive selection on disposable store copies.

The empty knowledge orchestrator captures its input; this is not answer-quality
evaluation. Session context/cooldowns are deliberately fresh for each query.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Sequence
from unittest.mock import patch

import numpy as np

from fram_eval.conversation_memory_eval import resolve_live_id_map
from fram_eval.fractal_autoflip import recommend_fractal_influence
from fram_eval.memory_shadow_eval import _cosine, _embed_text, _load_episode_vectors
from fram_serving import query_runner
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.lived_memory import LivedMemoryStore
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.observability import TraceLogWriter
from fram_serving.query_runner import QueryContext

_EVALUATION_LOCK = threading.Lock()
MODES = ("semantic", "lexical", "fractal")


def _private_json(value: Any) -> Any:
    """Explicitly preserve typed dataclass provenance; reject unknown objects."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "record_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _private_json(getattr(value, field.name))
                for field in dataclass_fields(value)
            },
        }
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("private capture mapping keys must be strings")
        return {key: _private_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_private_json(item) for item in value]
    raise TypeError(f"unsupported private capture type: {type(value).__qualname__}")


def _replace_progress(temporary: Path, destination: Path) -> None:
    """Keep receipts atomic across short Windows reader/scanner sharing locks."""
    for attempt in range(8):
        try:
            temporary.replace(destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 7:
                raise
            time.sleep(0.01 * 2**attempt)


def _write_progress(scratch_root: Path, progress: dict[str, Any]) -> None:
    """One bounded metadata receipt, atomically replaced after each query stage."""
    payload = {key: value for key, value in progress.items() if not key.startswith("_")}
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["elapsed_seconds"] = time.perf_counter() - progress["_started"]
    if progress.get("_active_started") is not None:
        payload["active_query_seconds"] = (
            time.perf_counter() - progress["_active_started"]
        )
    scratch_root.mkdir(parents=True, exist_ok=True)
    temporary = scratch_root / "production-progress.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _replace_progress(temporary, scratch_root / "production-progress.json")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _code_manifest(root: Path) -> dict[str, str]:
    """Fingerprint package Python sources, without inspecting runtime storage."""
    root = Path(root).resolve()
    paths = [root / "scripts" / "production_memory_eval.py"]
    excluded = {"storage", ".venv", "venv", "__pycache__", ".git"}
    for package in sorted(root.glob("fram_*")):
        if not package.is_dir():
            continue
        if package.is_symlink() or not package.resolve().is_relative_to(root):
            raise ValueError("source package link leaves repository")
        for directory, children, names in os.walk(package, followlinks=False):
            children[:] = sorted(name for name in children if name not in excluded)
            current = Path(directory)
            for name in children:
                child = current / name
                if child.is_symlink() or not child.resolve().is_relative_to(root):
                    raise ValueError("source directory link leaves repository")
            paths.extend(
                current / name for name in sorted(names) if name.endswith(".py")
            )
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("source file link leaves repository")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result


def tree_manifest(root: Path) -> dict[str, str]:
    """Hash every regular file; reject links rather than follow them out of scope."""
    root = Path(root).resolve()
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"source contains a link: {path}")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def snapshot_memory(source: Path, destination: Path) -> dict[str, Any]:
    """Copy a stable, supplied memory tree without initializing the source store.

    Source must already be an offline snapshot if it contains a lived SQLite DB;
    active WALs are rejected. Working sessions/capsules are outside this adapter.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if (
        source == destination
        or source.is_relative_to(destination)
        or destination.is_relative_to(source)
    ):
        raise ValueError("source and scratch must be disjoint")
    if not (source / "cognitive").is_dir():
        raise ValueError("source-memory-root must contain cognitive/")
    if destination.exists():
        raise ValueError("scratch snapshot destination must be new")
    for wal in source.glob("lived/*-wal"):
        if wal.stat().st_size:
            raise ValueError(
                "supply a consistent offline SQLite backup, not an active WAL"
            )
    before = tree_manifest(source)
    children = [
        p
        for p in source.iterdir()
        if p.is_dir()
        and (
            p.name in {"cognitive", "fractal", "lived"} or p.name.startswith("fractal_")
        )
    ]
    destination.mkdir(parents=True)
    for child in children:
        shutil.copytree(child, destination / child.name)
    after = tree_manifest(source)
    copied = tree_manifest(destination)
    expected = {
        name: digest
        for name, digest in before.items()
        if name.split("/")[0] in {p.name for p in children}
    }
    if before != after or copied != expected:
        raise RuntimeError("source changed during copy or snapshot bytes differ")
    return {
        "source_memory_root": str(source),
        "source_manifest": before,
        "copied_manifest": copied,
        "corpus_sha256": _digest(copied),
    }


def validate_config(config: FRAMConfig) -> None:
    for name, value in config.STORAGE_SUBFOLDERS.items():
        if Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError(f"storage subfolder must remain in scratch: {name}")
    if config.STORAGE_SUBFOLDERS.get("memory", "memory") != "memory":
        raise ValueError("adapter requires the standard memory/ layout")
    if config.phase_d.enabled:
        raise ValueError(
            "enabled Phase-D requires a separate real orchestrator adapter"
        )
    if config.memory_capsule_enabled or config.memory_capsule_retrieval_enabled:
        raise ValueError("capsule stages are not supported by this adapter")
    if config.enable_hard_forgetting:
        raise ValueError("hard forgetting is not permitted during evaluation")
    if config.cognitive_memory_k <= 0 or config.cognitive_memory_trace_k <= 0:
        raise ValueError("positive cognitive k and trace k are required for telemetry")
    if (
        not np.isfinite(config.cognitive_memory_half_life_hours)
        or config.cognitive_memory_half_life_hours < 0
    ):
        raise ValueError("half life must be finite and nonnegative")


class CaptureOrchestrator:
    """Capture actual selected chunks; do not perform document/answer selection."""

    def __init__(self) -> None:
        self.chunks: list[dict[str, Any]] = []
        self.delivered = False

    def run(self, text: str, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        self.chunks = deepcopy(kwargs.get("memory_chunks") or [])
        self.delivered = True
        record = {
            "id": uuid.uuid4().hex,
            "time": datetime.now(timezone.utc).isoformat(),
            "query": text,
            "citations": [],
            "domain": kwargs.get("domain"),
            "task": kwargs.get("task"),
            "trace": {"coverage": {}, "confidence": {}},
        }
        return {
            "trace_id": record["id"],
            "answer": "",
            "citations": [],
            "coverage": {},
            "record": record,
        }


def build_context(
    storage_root: Path, config: FRAMConfig, *, lexical: bool = False
) -> QueryContext:
    """Build a standalone context using only the caller's disposable storage root."""
    validate_config(config)
    storage_root = Path(storage_root).resolve()
    cfg = config.model_copy(
        update={"STORAGE_ROOT": storage_root, "mcp_cognitive_write_enabled": False}
    )
    memory_root = storage_root / "memory"
    vectorizer = build_cognitive_vectorizer(cfg)
    if vectorizer is None:
        raise ValueError(
            "configured vectorizer unavailable; refusing silent lexical fallback"
        )

    def encode(text: str) -> tuple[list[float], str]:
        matrix = vectorizer.transform([text])
        arr = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
        return np.asarray(
            arr, dtype=float
        ).ravel().tolist(), cfg.cognitive_memory_embedding_backend

    def sensitivity(task: str | None, domain: str | None) -> str:
        return str(
            cfg.time_sensitivity_task.get(task or "")
            or cfg.time_sensitivity_domain.get(domain or "")
            or "low"
        ).lower()

    lived = None
    if (
        cfg.lived_memory_enabled
        and (memory_root / "lived" / "lived_memory.sqlite3").is_file()
    ):
        lived = LivedMemoryStore(
            memory_root / "lived",
            target_dim=cfg.lived_memory_target_dim,
            fractal_nodes=cfg.lived_memory_fractal_nodes,
            scan_limit=cfg.lived_memory_scan_limit,
            state_decay=cfg.lived_memory_state_decay,
            busy_timeout_seconds=cfg.lived_memory_busy_timeout_seconds,
        )
    return QueryContext(
        cfg=cfg,
        orchestrator=CaptureOrchestrator(),
        memory_store=WorkingMemoryStore(memory_root / "working"),
        cognitive_store=CognitiveMemoryStore(memory_root / "cognitive", config=cfg),
        capsule_store=None,
        get_memory_vectorizer=lambda: None if lexical else vectorizer,
        encode_cognitive_text=encode,
        apply_phase_d_memory_bridge=lambda _text, candidates, _debug: (
            candidates,
            None,
        ),
        cooldown_active=lambda _id, _ts: False,
        register_cooldown=lambda _id, _ts: None,
        cooldown_window=timedelta(minutes=1),
        resolve_time_sensitivity=sensitivity,
        ensure_doc_cache=lambda: {},
        trace_writer=TraceLogWriter(storage_root / "traces"),
        observability_dir=storage_root / "observability",
        trace_dir=storage_root / "traces",
        store_prob=lambda *_args, **_kwargs: None,
        log_memory_event=lambda *_args, **_kwargs: None,
        archive_writer=None,
        archive_kind="query",
        cognitive_write_enabled=False,
        lived_memory_store=lived,
    )


def capture_selection(
    ctx: QueryContext, query: str, *, domain: str = "general", task: str = "qa"
) -> dict[str, Any]:
    """Capture full production telemetry and cross-check delivered chunks/prefix."""
    path = ctx.observability_dir / "memory_cognitive.jsonl"
    offset = path.stat().st_size if path.exists() else 0
    started = time.perf_counter()
    result = query_runner.run_query(
        SimpleNamespace(
            text=query,
            domain=domain,
            task=task,
            as_of=None,
            version_id=None,
            budget_reads=None,
            memory_session=None,
            principal=None,
        ),
        ctx,
    )
    elapsed = time.perf_counter() - started
    if result.get("cognitive_episode_write_ok") or result.get("lived_memory_write_ok"):
        raise RuntimeError("evaluation unexpectedly wrote a memory")
    if not path.exists():
        raise RuntimeError(
            "missing production cognitive telemetry (including possible refusal/error)"
        )
    with path.open("rb") as handle:
        handle.seek(offset)
        events = [json.loads(line) for line in handle if line.strip()]
    matches = [event for event in events if event.get("query_id") == result["id"]]
    if len(matches) != 1:
        raise RuntimeError("missing or ambiguous production cognitive telemetry")
    event = matches[0]
    selected = event["selected"]
    chunks = ctx.orchestrator.chunks
    ids = [entry["id"] for entry in selected]
    if ids != [chunk["file"] for chunk in chunks]:
        raise RuntimeError("telemetry IDs disagree with chunks actually delivered")
    prefix = result.get("trace", {}).get("cognitive_memory", {}).get("selected")
    if (
        prefix is None
        or [entry["id"] for entry in prefix] != ids[: ctx.cfg.cognitive_memory_trace_k]
    ):
        raise RuntimeError("production trace prefix disagrees with full selection")
    return {
        "selected": selected,
        "chunks": chunks,
        "elapsed_seconds": elapsed,
        "ann_bridge": event.get("ann_bridge"),
        "clock": event.get("clock"),
        "trace_prefix": prefix,
        "lived_store_present": ctx.lived_memory_store is not None,
    }


class ExactTraceCache:
    """Memoize the unchanged global scorer, including its normalization population.

    Used only within the single-threaded offline evaluator, never installed in a
    server. Hashing all trace bytes on every lookup prevents stale cache reuse.
    """

    def __init__(self, *, skip_off_observation: bool = False) -> None:
        self.original = query_runner._fractal_trace_scores
        self.values: dict[str, Any] = {}
        self.hits = 0
        self.misses = 0
        self.skip_off_observation = skip_off_observation
        self.off_observations_skipped = 0
        self.boundary_violations = 0
        self.active_orchestrator: CaptureOrchestrator | None = None

    def __call__(
        self, store: CognitiveMemoryStore, vector: Any, limit: int, cfg: FRAMConfig
    ) -> Any:
        if self.skip_off_observation and not cfg.fractal_influence_enabled:
            if (
                self.active_orchestrator is None
                or not self.active_orchestrator.delivered
            ):
                self.boundary_violations += 1
                raise RuntimeError("OFF scorer called before actual chunk delivery")
            self.off_observations_skipped += 1
            return []
        profile = cfg.model_dump(mode="json", exclude={"STORAGE_ROOT", "api_key"})
        traces = tree_manifest(store._fractal_storage_root)
        cognitive = tree_manifest(store.root)
        vector_meta = store._load_vector_meta(store._backend_key(None))
        key = _digest(
            {
                "profile": profile,
                "traces": traces,
                "cognitive": cognitive,
                "vector_meta": vector_meta,
                "vector": np.asarray(vector, dtype=float).tolist(),
                "limit": limit,
            }
        )
        if key in self.values:
            self.hits += 1
            return deepcopy(self.values[key])
        self.misses += 1
        result = self.original(store, vector, limit, cfg)
        self.values[key] = deepcopy(result)
        return result


@contextmanager
def isolated_evaluation(
    storage_root: Path, cache: ExactTraceCache, evaluation_time: datetime | None = None
) -> Iterator[None]:
    """Prevent concurrent environment/scorer patching in this offline process."""
    if not _EVALUATION_LOCK.acquire(blocking=False):
        raise RuntimeError("production evaluations must run in separate processes")
    values = {
        "FRAM_STORAGE_ROOT": str(storage_root),
        "COGMEM_STORAGE_ROOT": str(storage_root),
        "COGMEM_AUTOLOG": "0",
        "FRAM_DEV_PROFILE": "0",
        "FRAM_FRACTAL_INFLUENCE": "0",
    }
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, values))
            stack.enter_context(
                patch.object(query_runner, "_fractal_trace_scores", cache)
            )
            if evaluation_time is not None:

                class EvaluationDateTime(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return (
                            evaluation_time.astimezone(tz)
                            if tz is not None
                            else evaluation_time.astimezone().replace(tzinfo=None)
                        )

                for module in (
                    query_runner,
                    sys.modules[CognitiveMemoryStore.__module__],
                    sys.modules[LivedMemoryStore.__module__],
                ):
                    stack.enter_context(
                        patch.object(module, "datetime", EvaluationDateTime)
                    )
            yield
    finally:
        _EVALUATION_LOCK.release()


def evaluate_production(
    items: Sequence[dict[str, str]],
    *,
    source_memory_root: Path,
    scratch_root: Path,
    config: FRAMConfig,
    modes: Sequence[str] = MODES,
    fields: Sequence[str] = ("probe", "probe_low_lex"),
    max_items: int = 1,
    item_offset: int = 0,
    evaluation_time: str | None = None,
    skip_off_observation: bool = False,
    shadow_k: int = 3,
    shadow_max_chars: int = 2000,
) -> dict[str, Any]:
    """Evaluate with a bounded progress/error receipt, including source custody."""
    source_memory_root, scratch_root = (
        Path(source_memory_root).resolve(),
        Path(scratch_root).resolve(),
    )
    if scratch_root.exists():
        raise ValueError("scratch root must be new")
    if source_memory_root.is_relative_to(scratch_root) or scratch_root.is_relative_to(
        source_memory_root
    ):
        raise ValueError("source and scratch must be disjoint")
    initial = tree_manifest(source_memory_root)
    clock = (
        datetime.fromisoformat(evaluation_time)
        if evaluation_time
        else datetime.now(timezone.utc)
    )
    if clock.tzinfo is None:
        raise ValueError("evaluation_time must include a timezone")
    clock = clock.astimezone(timezone.utc)
    progress = {
        "schema": "production-cognitive-progress-v1",
        "status": "running",
        "phase": "snapshot",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "_started": time.perf_counter(),
        "_active_started": None,
        "queries_attempted": 0,
        "queries_selected": 0,
        "queries_persisted": 0,
        "selection_seconds": 0.0,
        "source_preservation": {
            "status": "not_checked_since_start",
            "initial_manifest_sha256": _digest(initial),
        },
    }
    try:
        report = _evaluate_production(
            items,
            source_memory_root=source_memory_root,
            scratch_root=scratch_root,
            config=config,
            modes=modes,
            fields=fields,
            max_items=max_items,
            item_offset=item_offset,
            evaluation_time=clock,
            skip_off_observation=skip_off_observation,
            shadow_k=shadow_k,
            shadow_max_chars=shadow_max_chars,
            _progress=progress,
        )
        progress.update(status="completed", phase="complete")
        return report
    except BaseException as exc:
        progress.update(status="failed", error_type=type(exc).__name__)
        # Exception strings may contain source bodies; stage/type remain bounded.
        raise
    finally:
        try:
            final = tree_manifest(source_memory_root)
            progress["source_preservation"] = {
                "status": "unchanged" if initial == final else "changed",
                "initial_manifest_sha256": _digest(initial),
                "final_manifest_sha256": _digest(final),
            }
        except Exception as exc:
            progress["source_preservation"]["status"] = "verification_failed"
            progress["source_preservation"]["error_type"] = type(exc).__name__
        late_preservation_failure = (
            progress["status"] == "completed"
            and progress["source_preservation"]["status"] != "unchanged"
        )
        if late_preservation_failure:
            progress.update(
                status="failed",
                phase="final_source_verification",
                error_type="RuntimeError",
            )
        _write_progress(scratch_root, progress)
        if late_preservation_failure:
            raise RuntimeError("final source preservation could not be verified")


def _evaluate_production(
    items: Sequence[dict[str, str]],
    *,
    source_memory_root: Path,
    scratch_root: Path,
    config: FRAMConfig,
    modes: Sequence[str],
    fields: Sequence[str],
    max_items: int,
    item_offset: int,
    evaluation_time: datetime,
    skip_off_observation: bool,
    shadow_k: int,
    shadow_max_chars: int,
    _progress: dict[str, Any],
) -> dict[str, Any]:
    """Run paired actual selections once; reuse captures for recall and shadow.

    max_items must be explicit/positive; the default is a one-item smoke. Public
    reports contain hashes, IDs, scores and aggregates, never memory bodies.
    """
    validate_config(config)
    if max_items <= 0 or item_offset < 0 or shadow_k <= 0 or shadow_max_chars <= 0:
        raise ValueError("positive item/snippet limits are required")
    if (
        not modes
        or len(set(modes)) != len(modes)
        or any(mode not in MODES for mode in modes)
    ):
        raise ValueError("unsupported or duplicate mode")
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("distinct query fields are required")
    if "fractal" in modes and not config.fractal_enabled:
        raise ValueError("fractal comparison requires explicit fractal_enabled=true")
    scratch_root = Path(scratch_root).resolve()
    if scratch_root.exists():
        raise ValueError("scratch root must be new")
    provenance = snapshot_memory(
        source_memory_root, scratch_root / "snapshot" / "memory"
    )
    _progress["phase"] = "initialize"
    _write_progress(scratch_root, _progress)
    chosen = list(items[item_offset : item_offset + max_items])
    if not chosen:
        raise ValueError("item range must select at least one dataset item")
    cache = ExactTraceCache(skip_off_observation=skip_off_observation)
    captures: list[dict[str, Any]] = []
    conversation: dict[str, Any] = {"results": {}}
    shadow: dict[str, Any] = {"results": {}}
    profile = config.model_dump(mode="json", exclude={"STORAGE_ROOT", "api_key"})
    code_root = Path(__file__).resolve().parents[1]
    code_manifest = _code_manifest(code_root)
    vectorizer = build_cognitive_vectorizer(config)
    if vectorizer is None:
        raise ValueError("configured vectorizer unavailable")
    with isolated_evaluation(scratch_root, cache, evaluation_time):
        matching_store = CognitiveMemoryStore(
            scratch_root / "snapshot" / "memory" / "cognitive",
            config=config.model_copy(update={"STORAGE_ROOT": scratch_root}),
        )
        id_map, matching = resolve_live_id_map(chosen, store=matching_store)
        vectors = _load_episode_vectors(matching_store)
        for mode in modes:
            storage = scratch_root / mode
            shutil.copytree(scratch_root / "snapshot" / "memory", storage / "memory")
            cfg = config.model_copy(
                update={"fractal_influence_enabled": mode == "fractal"}
            )
            conversation["results"][mode], shadow["results"][mode] = {}, {}
            for field in fields:
                rows, deltas = [], []
                missing_query = missing_expected = shadow_missing = 0
                for item in chosen:
                    query = str(item.get(field) or "")
                    if not query:
                        missing_query += 1
                        continue
                    expected = id_map.get(str(item.get("id")))
                    if not expected:
                        missing_expected += 1
                        continue
                    ctx = build_context(storage, cfg, lexical=mode == "lexical")
                    _progress.update(
                        phase="select",
                        active_mode=mode,
                        active_field=field,
                        active_query_sha256=hashlib.sha256(query.encode()).hexdigest(),
                        _active_started=time.perf_counter(),
                    )
                    _progress["queries_attempted"] += 1
                    _write_progress(scratch_root, _progress)
                    cache.active_orchestrator = ctx.orchestrator
                    capture = capture_selection(
                        ctx,
                        query,
                        domain=str(
                            item.get("domain") or item.get("match_domain") or "general"
                        ),
                        task=str(item.get("task") or item.get("match_task") or "qa"),
                    )
                    if cache.boundary_violations:
                        raise RuntimeError(
                            "OFF observation crossed the selection boundary"
                        )
                    _progress["queries_selected"] += 1
                    _progress["selection_seconds"] += capture["elapsed_seconds"]
                    _progress.update(
                        phase="metrics_and_private_capture", _active_started=None
                    )
                    _write_progress(scratch_root, _progress)
                    selected_ids = [entry["id"] for entry in capture["selected"]]
                    expected_doc = f"cmem:ep:{expected}"
                    rank = (
                        selected_ids.index(expected_doc)
                        if expected_doc in selected_ids
                        else None
                    )
                    snippet = "\n\n".join(
                        chunk["text"] for chunk in capture["chunks"][:shadow_k]
                    )[:shadow_max_chars]
                    expected_vec = vectors.get(expected)
                    base = _cosine(
                        _embed_text(query, vectorizer=vectorizer), expected_vec
                    )
                    augmented = _cosine(
                        _embed_text(
                            f"{query}\n\n{snippet}" if snippet else query,
                            vectorizer=vectorizer,
                        ),
                        expected_vec,
                    )
                    delta = (
                        augmented - base
                        if base is not None and augmented is not None
                        else None
                    )
                    if delta is None:
                        shadow_missing += 1
                    else:
                        deltas.append(delta)
                    selected_public = [
                        {
                            key: entry[key]
                            for key in (
                                "id",
                                "kind",
                                "score",
                                "score_raw",
                                "base_score",
                                "fractal_score",
                                "fractal_influence",
                                "combined_score",
                                "recency_weight",
                                "tokens",
                            )
                            if key in entry
                        }
                        for entry in capture["selected"]
                    ]
                    ann_public = {
                        key: value
                        for key, value in (capture["ann_bridge"] or {}).items()
                        if key
                        in {
                            "enabled",
                            "applied",
                            "bridge_disabled_reason",
                            "ann_used",
                            "index_backend",
                            "index_size",
                            "returned",
                            "backend",
                            "vector_count",
                            "expected_dim",
                            "query_dim",
                        }
                    }
                    row = {
                        "mode": mode,
                        "field": field,
                        "item_id": str(item.get("id")),
                        "source_corpus_sha256": provenance["corpus_sha256"],
                        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                        "expected_id": expected_doc,
                        "rank": rank,
                        "selected": selected_public,
                        "delta": delta,
                        "snippet_sha256": hashlib.sha256(snippet.encode()).hexdigest(),
                        "elapsed_seconds": capture["elapsed_seconds"],
                        "clock": capture["clock"],
                        "lived_store_present": capture["lived_store_present"],
                        "ann_bridge": ann_public,
                    }
                    rows.append(row)
                    captures.append(row)
                    private_line = (
                        json.dumps(
                            _private_json(
                                {**row, "query": query, "chunks": capture["chunks"]}
                            )
                        )
                        + "\n"
                    )
                    with (scratch_root / "private-captures.jsonl").open(
                        "a", encoding="utf-8"
                    ) as handle:
                        handle.write(private_line)
                    _progress["queries_persisted"] += 1
                    _progress["phase"] = "query_complete"
                    _write_progress(scratch_root, _progress)
                count = len(rows)
                conversation["results"][mode][field] = {
                    "count": count,
                    "top1": sum(row["rank"] == 0 for row in rows) / count
                    if count
                    else 0.0,
                    "top3": sum(
                        row["rank"] is not None and row["rank"] < 3 for row in rows
                    )
                    / count
                    if count
                    else 0.0,
                    "missing_query": missing_query,
                    "missing_expected": missing_expected,
                }
                shadow["results"][mode][field] = {
                    "count": len(deltas),
                    "avg_delta": float(np.mean(deltas)) if deltas else 0.0,
                    "missing_vectors": shadow_missing,
                    "missing_query": missing_query,
                    "missing_expected": missing_expected,
                }
    _progress["phase"] = "verify_source_and_code"
    _write_progress(scratch_root, _progress)
    if tree_manifest(Path(source_memory_root)) != provenance["source_manifest"]:
        raise RuntimeError("source changed during evaluation")
    if _code_manifest(code_root) != code_manifest:
        raise RuntimeError("evaluation code changed during the run")
    return {
        "schema": "production-cognitive-selection-v1",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "claim": "actual run_query cognitive selection; not end-to-end answer quality",
        "context": (
            "stateless queries, no session or cooldown history; empty knowledge index"
        ),
        "mode_meanings": {
            "semantic": "configured vectorizer, influence off",
            "lexical": (
                "base search vectorizer absent (ANN bridge cannot return); "
                "configured lived recall retained"
            ),
            "fractal": (
                "configured vectorizer, influence on; unchanged global trace scorer"
            ),
        },
        "profile": profile,
        "profile_sha256": _digest(profile),
        "provenance": provenance,
        "code_manifest": code_manifest,
        "code_sha256": _digest(code_manifest),
        "runtime": {"python": sys.version, "numpy": np.__version__},
        "evaluation_time": evaluation_time.isoformat(),
        "observation_policy": (
            "skip_off_after_chunk_delivery" if skip_off_observation else "full"
        ),
        "dataset_sha256": _digest(list(items)),
        "max_items": max_items,
        "matching": matching,
        "resolved_targets": id_map,
        "item_range": {
            "start": item_offset,
            "stop": item_offset + len(chosen),
            "count": len(chosen),
        },
        "full_dataset_evaluated": len(chosen) == len(items),
        "shadow_snippet": {"selected_prefix": shadow_k, "max_chars": shadow_max_chars},
        "ann_backend_env": os.getenv("FRAM_ANN_BACKEND"),
        "trace_cache": {
            "hits": cache.hits,
            "misses": cache.misses,
            "entries": len(cache.values),
            "off_observations_skipped": cache.off_observations_skipped,
            "boundary_violations": cache.boundary_violations,
        },
        "conversation": conversation,
        "shadow": shadow,
        "captures": captures,
        "source_unchanged": True,
        "lived_scope": (
            "copied supplied database if present; "
            "never another source merged implicitly"
        ),
    }


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and bool(np.isfinite(value))
    )


def _capture_metrics(
    captures: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute from individual delivered selections, never shard averages."""
    conversation, shadow = {"results": {}}, {"results": {}}
    for mode in MODES:
        conversation["results"][mode], shadow["results"][mode] = {}, {}
        for field in ("probe", "probe_low_lex"):
            rows = [
                row for row in captures if row["mode"] == mode and row["field"] == field
            ]
            ranks = []
            for row in rows:
                ids = [entry["id"] for entry in row["selected"]]
                ranks.append(
                    ids.index(row["expected_id"]) if row["expected_id"] in ids else None
                )
            deltas = [row["delta"] for row in rows if _finite(row.get("delta"))]
            conversation["results"][mode][field] = {
                "count": len(rows),
                "top1": sum(rank == 0 for rank in ranks) / len(rows) if rows else 0.0,
                "top3": sum(rank is not None and rank < 3 for rank in ranks) / len(rows)
                if rows
                else 0.0,
                "missing_query": 0,
                "missing_expected": 0,
            }
            shadow["results"][mode][field] = {
                "count": len(deltas),
                "avg_delta": float(np.mean(deltas)) if deltas else 0.0,
                "missing_vectors": len(rows) - len(deltas),
                "missing_query": 0,
                "missing_expected": 0,
            }
    return conversation, shadow


def _scope_errors(report: dict[str, Any], items: Sequence[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    try:
        if report.get("schema") != "production-cognitive-selection-v1":
            errors.append("missing completed production report")
        if report.get("dataset_sha256") != _digest(list(items)):
            errors.append("dataset fingerprint mismatch")
        if not report.get("source_unchanged"):
            errors.append("source preservation not verified")
        if not report.get("full_dataset_evaluated"):
            errors.append("partial dataset scope")
        if report["trace_cache"].get("boundary_violations", 0):
            errors.append("observation crossed selection boundary")
        matching = report["matching"]
        if (
            matching.get("total") != len(items)
            or matching.get("matched") != len(items)
            or matching.get("missing") != 0
            or matching.get("ambiguous") != 0
        ):
            errors.append("incomplete or ambiguous target coverage")
        item_ids = [str(item.get("id") or "") for item in items]
        if (
            not items
            or any(not item_id for item_id in item_ids)
            or len(set(item_ids)) != len(item_ids)
        ):
            errors.append("empty or duplicate dataset item IDs")
        targets = report["resolved_targets"]
        if set(targets) != set(item_ids):
            errors.append("resolved target set differs from dataset")
        expected = set()
        for item in items:
            item_id = str(item.get("id") or "")
            target = targets.get(item_id)
            if not target or (
                item.get("match_episode_id") and target != item["match_episode_id"]
            ):
                errors.append("missing or incorrect expected target ID")
            for field in ("probe", "probe_low_lex"):
                query = str(item.get(field) or "")
                if not query:
                    errors.append("dataset query missing")
                for mode in MODES:
                    expected.add(
                        (
                            mode,
                            field,
                            item_id,
                            hashlib.sha256(query.encode()).hexdigest(),
                            f"cmem:ep:{target}",
                        )
                    )
        actual = []
        for row in report["captures"]:
            actual.append(
                (
                    row["mode"],
                    row["field"],
                    row["item_id"],
                    row["query_sha256"],
                    row["expected_id"],
                )
            )
            if row.get("source_corpus_sha256") != report["provenance"]["corpus_sha256"]:
                errors.append("capture source fingerprint mismatch")
            if row.get("clock", {}).get("utc_iso") != report.get("evaluation_time"):
                errors.append("capture evaluation clock mismatch")
            if not _finite(row.get("delta")) or not _finite(row.get("elapsed_seconds")):
                errors.append("nonfinite or missing per-query metric")
            ids = [entry["id"] for entry in row["selected"]]
            rank = ids.index(row["expected_id"]) if row["expected_id"] in ids else None
            if row.get("rank") != rank or len(ids) != len(set(ids)):
                errors.append("captured rank or selected IDs inconsistent")
            for entry in row["selected"]:
                if any(
                    not _finite(entry.get(key))
                    for key in (
                        "score",
                        "score_raw",
                        "base_score",
                        "fractal_score",
                        "combined_score",
                        "recency_weight",
                    )
                ):
                    errors.append("nonfinite or missing selected score")
        if set(actual) != expected or len(actual) != len(expected):
            errors.append("paired item/query/expected-ID row coverage mismatch")
        recalculated = _capture_metrics(report["captures"])
        for name, recomputed in zip(("conversation", "shadow"), recalculated):
            if set(report[name]["results"]) != set(MODES):
                errors.append("missing paired mode")
            for mode in MODES:
                if set(report[name]["results"].get(mode, {})) != {
                    "probe",
                    "probe_low_lex",
                }:
                    errors.append("missing paired query field")
                for field in ("probe", "probe_low_lex"):
                    metric = report[name]["results"][mode][field]
                    required = (
                        ("count", "top1", "top3")
                        if name == "conversation"
                        else ("count", "avg_delta")
                    )
                    for key in required:
                        value = metric.get(key)
                        if not _finite(value) or not np.isclose(
                            value,
                            recomputed["results"][mode][field][key],
                            rtol=0,
                            atol=1e-12,
                        ):
                            errors.append("nonfinite or inconsistent aggregate metric")
                    if metric.get("count") != len(items):
                        errors.append("metric count differs from full dataset")
                    for key in ("missing_query", "missing_expected") + (
                        ("missing_vectors",) if name == "shadow" else ()
                    ):
                        if metric.get(key) != 0:
                            errors.append("query, target, or vector missing")
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append("malformed or incomplete production evidence")
    return sorted(set(errors))


def strict_production_gate(
    report: dict[str, Any], items: Sequence[dict[str, str]]
) -> dict[str, Any]:
    """Keep historical margins, but require exact complete paired evidence first."""
    errors = _scope_errors(report, items)
    gate = recommend_fractal_influence(
        report.get("conversation", {}),
        report.get("shadow", {}),
        fields=("probe", "probe_low_lex"),
        low_lex_fields=("probe_low_lex",),
    )
    gate["production_scope_complete"] = not errors
    gate["scope_errors"] = errors
    if errors:
        gate["recommend_enable"] = False
        gate["reasons"].extend(errors)
    return gate


def merge_production_reports(
    reports: Sequence[dict[str, Any]],
    *,
    items: Sequence[dict[str, str]],
    expected_shards: int,
) -> dict[str, Any]:
    """Validate independent shards and aggregate only their public captures."""
    if expected_shards < 1 or len(reports) != expected_shards:
        raise ValueError("failed or missing shard")
    base = reports[0]
    shared = (
        "schema",
        "profile_sha256",
        "profile",
        "provenance",
        "code_manifest",
        "code_sha256",
        "dataset_sha256",
        "evaluation_time",
        "observation_policy",
        "shadow_snippet",
        "mode_meanings",
        "runtime",
        "ann_backend_env",
    )
    covered, captures, targets = set(), [], {}
    totals = {
        key: 0 for key in ("total", "matched", "matched_by_id", "missing", "ambiguous")
    }
    for report in reports:
        if any(report.get(key) != base.get(key) for key in shared):
            raise ValueError("shard source/profile/code/dataset/clock policy mismatch")
        if report.get(
            "schema"
        ) != "production-cognitive-selection-v1" or not report.get("source_unchanged"):
            raise ValueError("failed shard or unverified source preservation")
        if report["dataset_sha256"] != _digest(list(items)):
            raise ValueError("shards do not reference the original complete dataset")
        bounds = report["item_range"]
        start, stop = bounds["start"], bounds["stop"]
        if (
            not isinstance(start, int)
            or not isinstance(stop, int)
            or start < 0
            or stop > len(items)
            or stop <= start
            or bounds["count"] != stop - start
        ):
            raise ValueError("invalid shard range")
        interval = set(range(start, stop))
        if covered & interval:
            raise ValueError("duplicate or overlapping shard range")
        # Validate each slice at full strength before combining its evidence.
        local = deepcopy(report)
        local["dataset_sha256"] = _digest(list(items[start:stop]))
        local["full_dataset_evaluated"] = True
        if _scope_errors(local, items[start:stop]):
            raise ValueError("failed or incomplete shard evidence")
        covered.update(interval)
        captures.extend(deepcopy(report["captures"]))
        targets.update(report["resolved_targets"])
        for key in totals:
            totals[key] += report["matching"][key]
    if covered != set(range(len(items))):
        raise ValueError("missing dataset range")
    order = {str(item["id"]): index for index, item in enumerate(items)}
    captures.sort(
        key=lambda row: (
            MODES.index(row["mode"]),
            ("probe", "probe_low_lex").index(row["field"]),
            order[row["item_id"]],
        )
    )
    merged = {key: deepcopy(value) for key, value in base.items() if key != "autoflip"}
    merged.update(
        captures=captures,
        resolved_targets=targets,
        matching=totals,
        full_dataset_evaluated=True,
        max_items=len(items),
        item_range={"start": 0, "stop": len(items), "count": len(items)},
        run_at=datetime.now(timezone.utc).isoformat(),
        merged_shards=len(reports),
    )
    merged["conversation"], merged["shadow"] = _capture_metrics(captures)
    merged["trace_cache"] = {
        key: sum(report["trace_cache"].get(key, 0) for report in reports)
        for key in (
            "hits",
            "misses",
            "entries",
            "off_observations_skipped",
            "boundary_violations",
        )
    }
    if _scope_errors(merged, items):
        raise ValueError("merged evidence does not cover the complete paired dataset")
    return merged
