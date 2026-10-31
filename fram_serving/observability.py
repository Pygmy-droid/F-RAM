"""Observability helpers for reliability curves and latency logs (spec section 17)."""

from __future__ import annotations

import json
import math
import uuid
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from fram_core.confidence import reliability_bins


def _append_jsonl(folder: Path, filename: str, payload: Dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    enriched = dict(payload)
    enriched.setdefault("time", datetime.now(timezone.utc).isoformat())
    try:
        with (folder / filename).open("a", encoding="utf-8") as f:
            f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    except Exception:
        # Observability must not break the main flow.
        pass


def log_confidence_event(root: Path, event: Dict[str, Any]) -> None:
    _append_jsonl(root, "confidence.jsonl", event)


def log_latency_event(root: Path, event: Dict[str, Any]) -> None:
    _append_jsonl(root, "latency.jsonl", event)


def log_memory_event(root: Path, event: Dict[str, Any]) -> None:
    _append_jsonl(root, "memory_sessions.jsonl", event)


def log_cognitive_memory_event(root: Path, event: Dict[str, Any]) -> None:
    _append_jsonl(root, "memory_cognitive.jsonl", event)


def log_fractal_memory_event(root: Path, event: Dict[str, Any]) -> None:
    _append_jsonl(root, "memory_fractal.jsonl", event)


_MEMORY_SEARCH_WINDOW_FILENAME = "memory_search.json"
_TC_WINDOW_FILENAME = "transitional_complexity_window.json"
_TC_ROUTING_WINDOW_FILENAME = "tc_routing_window.json"


def _coerce_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _linear_percentile(sorted_values: List[float], p: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    p_clamped = max(0.0, min(1.0, float(p)))
    pos = p_clamped * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    frac = pos - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


def summarize_numeric_window(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "p50": None,
            "p95": None,
        }
    clean = [float(v) for v in values if math.isfinite(float(v))]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "p50": None,
            "p95": None,
        }
    mean = sum(clean) / len(clean)
    var = sum((v - mean) ** 2 for v in clean) / len(clean)
    std = math.sqrt(var)
    ordered = sorted(clean)
    return {
        "count": int(len(clean)),
        "min": float(ordered[0]),
        "max": float(ordered[-1]),
        "mean": float(mean),
        "std": float(std),
        "p50": _linear_percentile(ordered, 0.5),
        "p95": _linear_percentile(ordered, 0.95),
    }


def _load_tc_window(root: Path, filename: str) -> Dict[str, Any] | None:
    path = Path(root) / filename
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _update_tc_window(
    root: Path,
    entry: Mapping[str, Any],
    *,
    maxlen: int,
    filename: str,
    name: str,
) -> Dict[str, Any] | None:
    tc_value = _coerce_finite_float(entry.get("tc"))
    if tc_value is None:
        return None
    maxlen_int = max(1, int(maxlen))
    root_path = Path(root)
    path = root_path / filename
    series: List[Dict[str, Any]] = []
    prior = _load_tc_window(root_path, filename)
    if isinstance(prior, dict):
        existing = prior.get("series")
        if isinstance(existing, list):
            series = [item for item in existing if isinstance(item, dict)]

    cleaned: Dict[str, Any] = {
        "time": entry.get("time") or datetime.now(timezone.utc).isoformat(),
        "query_id": entry.get("query_id"),
        "stream": entry.get("stream"),
        "step": entry.get("step"),
        "dim": entry.get("dim"),
        "tc": float(tc_value),
    }
    for key in ("delta_l2", "delta_entropy", "curvature_l2"):
        value = _coerce_finite_float(entry.get(key))
        if value is not None:
            cleaned[key] = float(value)
    series.append(cleaned)
    if len(series) > maxlen_int:
        series = series[-maxlen_int:]

    values = [float(item.get("tc", 0.0)) for item in series if _coerce_finite_float(item.get("tc")) is not None]
    stats = summarize_numeric_window(values)
    snapshot: Dict[str, Any] = {
        "schema_version": "tc-window-1",
        "name": str(name),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "window_max": int(maxlen_int),
        "window_size": int(len(series)),
        "latest": float(series[-1]["tc"]) if series else None,
        "stats": stats,
        "series": series,
    }
    try:
        root_path.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        return None
    return snapshot


def update_memory_search_window(
    root: Path,
    entry: Mapping[str, Any],
    *,
    maxlen: int = 200,
) -> Dict[str, Any] | None:
    """Persist a bounded cognitive memory search snapshot under `storage/observability`."""
    root_path = Path(root)
    path = root_path / _MEMORY_SEARCH_WINDOW_FILENAME
    series: List[Dict[str, Any]] = []
    if path.exists():
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
        if isinstance(prior, dict):
            existing = prior.get("series")
            if isinstance(existing, list):
                series = [item for item in existing if isinstance(item, dict)]

    cleaned: Dict[str, Any] = {
        "time": entry.get("time") or datetime.now(timezone.utc).isoformat(),
        "query_preview": entry.get("query_preview"),
        "backend": entry.get("backend"),
        "results": entry.get("results"),
        "selected_total": entry.get("selected_total"),
        "selected_used": entry.get("selected_used"),
        "selected_dropped": entry.get("selected_dropped"),
        "token_budget": entry.get("token_budget"),
        "slot_budget": entry.get("slot_budget"),
        "ann_enabled": entry.get("ann_enabled"),
        "ann_returned": entry.get("ann_returned"),
        "ann_backend": entry.get("ann_backend"),
        "ann_requested": entry.get("ann_requested"),
        "ann_index_size": entry.get("ann_index_size"),
        "ann_reason": entry.get("ann_reason"),
    }
    series.append(cleaned)
    maxlen_int = max(1, int(maxlen))
    if len(series) > maxlen_int:
        series = series[-maxlen_int:]

    def _avg(key: str) -> float | None:
        values = [item.get(key) for item in series if isinstance(item.get(key), (int, float))]
        if not values:
            return None
        return float(sum(values) / len(values))

    ann_enabled_count = sum(1 for item in series if item.get("ann_enabled"))
    snapshot: Dict[str, Any] = {
        "schema_version": "memory-search-1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "window_max": maxlen_int,
        "window_size": len(series),
        "stats": {
            "events": len(series),
            "avg_results": _avg("results"),
            "avg_selected_total": _avg("selected_total"),
            "avg_selected_used": _avg("selected_used"),
            "avg_selected_dropped": _avg("selected_dropped"),
            "ann_enabled_rate": ann_enabled_count / len(series) if series else 0.0,
        },
        "series": series,
    }
    try:
        root_path.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        return None
    return snapshot


def load_transitional_complexity_window(root: Path) -> Dict[str, Any] | None:
    return _load_tc_window(root, _TC_WINDOW_FILENAME)


def load_tc_routing_window(root: Path) -> Dict[str, Any] | None:
    return _load_tc_window(root, _TC_ROUTING_WINDOW_FILENAME)


def update_transitional_complexity_window(
    root: Path,
    entry: Mapping[str, Any],
    *,
    maxlen: int = 500,
) -> Dict[str, Any] | None:
    """Persist a bounded TC time-series snapshot under `storage/observability`.

    Best-effort only: failures are swallowed so observability never breaks the main flow.
    """

    return _update_tc_window(
        root,
        entry,
        maxlen=maxlen,
        filename=_TC_WINDOW_FILENAME,
        name="transitional_complexity",
    )


def update_tc_routing_window(
    root: Path,
    entry: Mapping[str, Any],
    *,
    maxlen: int = 500,
) -> Dict[str, Any] | None:
    return _update_tc_window(
        root,
        entry,
        maxlen=maxlen,
        filename=_TC_ROUTING_WINDOW_FILENAME,
        name="tc_routing",
    )


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_recent_traces(root: Path, limit: int = 100) -> List[dict]:
    traces_dir = root / "traces"
    files = sorted(traces_dir.glob("*.jsonl"), reverse=True)
    traces: List[dict] = []
    for file in files:
        for record in reversed(list(iter_jsonl(file))):
            traces.append(record)
            if len(traces) >= limit:
                return traces
    return traces


def as_of_delta_summary(root: Path, limit: int = 50) -> Dict[str, Any]:
    """
    Summarize recent as-of filters and delta snippets for a compact observability view.
    """
    traces = load_recent_traces(root, limit=limit * 2)
    items: List[Dict[str, Any]] = []
    for trace in traces:
        asof_block = trace.get("as_of_filter") or {}
        delta_snippets = trace.get("delta_snippets") or trace.get("delta_snippet") or []
        if not asof_block and not delta_snippets:
            continue
        deltas = delta_snippets if isinstance(delta_snippets, list) else [delta_snippets]
        preview: Optional[Any] = None
        if deltas:
            first = deltas[0]
            if isinstance(first, Mapping):
                preview = first.get("diff") or first
            else:
                preview = first
        nodes = asof_block.get("active_nodes") or []
        items.append(
            {
                "id": trace.get("id") or trace.get("query_id"),
                "time": trace.get("time"),
                "as_of": asof_block.get("as_of") or trace.get("as_of"),
                "active_nodes": nodes,
                "active_count": len(nodes),
                "dropped_candidates": asof_block.get("dropped_candidates"),
                "delta_count": len(deltas),
                "delta_preview": preview,
            }
        )
        if len(items) >= limit:
            break
    return {"items": items, "total": len(items)}


def summarize_traces(traces: Iterable[dict]) -> Dict[str, Any]:
    total = 0
    decisions: Dict[str, int] = {}
    facts_total = 0.0
    memory_usage = 0.0
    coverage_total = 0.0
    coverage_stage_totals: Dict[str, float] = {
        "memory": 0.0,
        "seed": 0.0,
        "anchors": 0.0,
        "shards": 0.0,
    }
    budget_totals = {"reads": 0.0, "tokens": 0.0, "pairs": 0.0, "cost": 0.0}
    cognitive_selected_total = 0.0
    cognitive_tokens_total = 0.0
    cognitive_invocations = 0

    for record in traces:
        total += 1
        trace = record.get("trace", {})
        decision = trace.get("confidence", {}).get("decision", "unknown")
        decisions[decision] = decisions.get(decision, 0) + 1

        coverage = trace.get("coverage", {}) or {}
        selection = trace.get("selection", {}) or {}

        coverage_delta = coverage.get("delta_total")
        if coverage_delta is None:
            coverage_delta = selection.get("coverage_delta", {}).get("total")
        if isinstance(coverage_delta, (int, float)):
            coverage_total += float(coverage_delta)

        stage_deltas = coverage.get("delta_by_stage") or selection.get("coverage_delta") or {}
        if isinstance(stage_deltas, dict):
            for key, value in stage_deltas.items():
                if isinstance(value, (int, float)):
                    coverage_stage_totals.setdefault(key, 0.0)
                    coverage_stage_totals[key] += float(value)

        coverage_budgets = coverage.get("budgets")
        if not isinstance(coverage_budgets, dict):
            coverage_budgets = selection.get("budgets")
        if isinstance(coverage_budgets, dict):
            for key in budget_totals:
                value = coverage_budgets.get(key)
                if isinstance(value, (int, float)):
                    budget_totals[key] += float(value)

        facts_value = coverage.get("facts_added")
        if isinstance(facts_value, (int, float)):
            facts_total += float(facts_value)

        memory = trace.get("memory") or {}
        memory_used = memory.get("used")
        if not isinstance(memory_used, (int, float)):
            memory_used = memory.get("count")
        if isinstance(memory_used, (int, float)):
            memory_usage += float(memory_used)
        cognitive = trace.get("cognitive_memory") or {}
        if isinstance(cognitive, dict):
            selected_list = cognitive.get("selected") or []
            if isinstance(selected_list, list) and selected_list:
                cognitive_invocations += 1
                cognitive_selected_total += float(len(selected_list))
                for entry in selected_list:
                    tokens = 0.0
                    if isinstance(entry, dict):
                        tokens = entry.get("tokens", 0.0)
                    if isinstance(tokens, (int, float)):
                        cognitive_tokens_total += float(tokens)

    avg_facts = facts_total / total if total else 0.0
    avg_memory = memory_usage / total if total else 0.0
    avg_total_delta = coverage_total / total if total else 0.0
    avg_stage_delta = {
        key: (value / total if total else 0.0) for key, value in coverage_stage_totals.items()
    }
    avg_budgets = {key: (value / total if total else 0.0) for key, value in budget_totals.items()}
    avg_cog_selected = (
        cognitive_selected_total / cognitive_invocations if cognitive_invocations else 0.0
    )
    avg_cog_tokens = (
        cognitive_tokens_total / cognitive_invocations if cognitive_invocations else 0.0
    )

    return {
        "total_traces": total,
        "decisions": decisions,
        "avg_facts_added": avg_facts,
        "avg_memory_used": avg_memory,
        "coverage_deltas": {
            "avg_total": avg_total_delta,
            "avg_by_stage": avg_stage_delta,
        },
        "avg_budgets": avg_budgets,
        "cognitive_memory": {
            "invocations": cognitive_invocations,
            "avg_selected": avg_cog_selected,
            "avg_tokens": avg_cog_tokens,
        },
    }


class LiveReliability:
    """Online reliability tracking for the last N labeled decisions (spec section 17)."""

    def __init__(self, maxlen: int = 500) -> None:
        self._records: deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._last_update: Optional[datetime] = None

    def update(
        self,
        item_id: str,
        prob: float,
        label: int,
        *,
        tau1: Optional[float] = None,
        tau2: Optional[float] = None,
        domain: Optional[str] = None,
        task: Optional[str] = None,
        source: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> None:
        entry = {"id": item_id, "p": float(prob), "y": int(bool(label))}
        if tau1 is not None:
            entry["tau1"] = float(tau1)
        if tau2 is not None:
            entry["tau2"] = float(tau2)
        if domain:
            entry["domain"] = str(domain)
        if task:
            entry["task"] = str(task)
        if source:
            entry["source"] = str(source)
        if temperature is not None:
            try:
                entry["temperature"] = float(temperature)
            except (TypeError, ValueError):
                pass
        if item_id in self._by_id:
            existing = self._by_id.pop(item_id)
            try:
                self._records.remove(existing)
            except ValueError:
                pass
        if self._records.maxlen is not None and len(self._records) >= self._records.maxlen:
            old = self._records.popleft()
            self._by_id.pop(old["id"], None)
        self._records.append(entry)
        self._by_id[item_id] = entry
        self._last_update = datetime.now(timezone.utc)


    def ece(self, n_bins: int = 15) -> tuple[float, list[dict[str, float]]]:
        if not self._records:
            return 0.0, []
        probs = [rec["p"] for rec in self._records]
        labels = [rec["y"] for rec in self._records]
        diag = reliability_bins(probs, labels, n_bins=n_bins)
        bins = diag.get("bins", [])
        return float(diag.get("ece", 0.0)), [dict(bin_) for bin_ in bins]

    def fn_rate_above(self, tau: Optional[float], *, tau_field: Optional[str] = None) -> float:
        if not self._records:
            return 0.0
        if tau_field:
            candidates = []
            for rec in self._records:
                value = rec.get(tau_field)
                if value is None:
                    continue
                try:
                    tau_value = float(value)
                except (TypeError, ValueError):
                    continue
                if rec["p"] >= tau_value:
                    candidates.append(rec)
            if candidates:
                misses = sum(1 for rec in candidates if rec["y"] == 0)
                return misses / len(candidates)
        if tau is None:
            return 0.0
        tau_val = float(tau)
        candidates = [rec for rec in self._records if rec["p"] >= tau_val]
        if not candidates:
            return 0.0
        misses = sum(1 for rec in candidates if rec["y"] == 0)
        return misses / len(candidates)


    def group_summary(self, field: str) -> Dict[str, Dict[str, Any]]:
        if not self._records:
            return {}

        aggregates: Dict[str, Dict[str, Any]] = {}

        for rec in self._records:
            raw_key = rec.get(field, "unknown")
            key = str(raw_key).strip().lower() or "unknown"
            bucket = aggregates.setdefault(
                key,
                {
                    "count": 0,
                    "positives": 0,
                    "prob_sum": 0.0,
                    "tau1_sum": 0.0,
                    "tau1_count": 0,
                    "tau2_sum": 0.0,
                    "tau2_count": 0,
                    "temperature_sum": 0.0,
                    "temperature_count": 0,
                    "sources": Counter(),
                },
            )

            bucket["count"] += 1
            if int(rec.get("y", 0)) == 1:
                bucket["positives"] += 1
            bucket["prob_sum"] += float(rec.get("p", 0.0))

            tau1_val = rec.get("tau1")
            if tau1_val is not None:
                try:
                    bucket["tau1_sum"] += float(tau1_val)
                    bucket["tau1_count"] += 1
                except (TypeError, ValueError):
                    pass

            tau2_val = rec.get("tau2")
            if tau2_val is not None:
                try:
                    bucket["tau2_sum"] += float(tau2_val)
                    bucket["tau2_count"] += 1
                except (TypeError, ValueError):
                    pass

            temp_val = rec.get("temperature")
            if temp_val is not None:
                try:
                    bucket["temperature_sum"] += float(temp_val)
                    bucket["temperature_count"] += 1
                except (TypeError, ValueError):
                    pass

            src_val = rec.get("source")
            if src_val:
                bucket["sources"][str(src_val)] += 1

        summary: Dict[str, Dict[str, Any]] = {}
        for key, data in aggregates.items():
            count = data["count"]
            if count == 0:
                continue

            entry: Dict[str, Any] = {
                "count": count,
                "positive_rate": data["positives"] / count,
                "avg_prob": data["prob_sum"] / count,
            }

            if data["tau1_count"]:
                entry["avg_tau1"] = data["tau1_sum"] / data["tau1_count"]
            if data["tau2_count"]:
                entry["avg_tau2"] = data["tau2_sum"] / data["tau2_count"]
            if data["temperature_count"]:
                entry["avg_temperature"] = data["temperature_sum"] / data["temperature_count"]
            if data["sources"]:
                entry["sources"] = dict(data["sources"])

            summary[key] = entry

        return dict(sorted(summary.items()))

    def latest(self) -> Optional[Dict[str, Any]]:
        if not self._records:
            return None
        return dict(self._records[-1])


    def __len__(self) -> int:
        return len(self._records)

    @property
    def capacity(self) -> Optional[int]:
        return self._records.maxlen

    @property
    def last_update(self) -> Optional[datetime]:
        return self._last_update

    def clear(self) -> None:
        self._records.clear()
        self._by_id.clear()
        self._last_update = None


class AlarmBook:
    """Evaluates live calibration alarms for observability dashboards."""

    def __init__(self, alpha1: float, alpha2: float, ece_limit: float = 0.03) -> None:
        self.alpha1 = float(alpha1)
        self.alpha2 = float(alpha2)
        self.ece_limit = float(ece_limit)
        self.flags: Dict[str, bool] = {"ece": False, "fn_tau1": False, "fn_tau2": False}
        self.last_metrics: Dict[str, float] = {"ece": 0.0, "fn_tau1": 0.0, "fn_tau2": 0.0}

    def evaluate(self, tracker: LiveReliability, tau1: Optional[float], tau2: Optional[float]) -> None:
        ece, _ = tracker.ece()
        fn1 = tracker.fn_rate_above(tau1, tau_field="tau1")
        fn2 = tracker.fn_rate_above(tau2, tau_field="tau2")
        self.last_metrics = {"ece": float(ece), "fn_tau1": float(fn1), "fn_tau2": float(fn2)}
        self.flags = {
            "ece": ece > self.ece_limit,
            "fn_tau1": fn1 > self.alpha1,
            "fn_tau2": fn2 > self.alpha2,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flags": dict(self.flags),
            "metrics": dict(self.last_metrics),
            "limits": {"ece": self.ece_limit, "alpha1": self.alpha1, "alpha2": self.alpha2},
        }


class TraceLogWriter:
    """Append orchestration traces to JSONL files for observability dashboards."""

    def __init__(
        self,
        base_dir: Path,
        *,
        prefix: str = "trace",
        daily_rollover: bool = True,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._prefix = prefix
        self._daily_rollover = bool(daily_rollover)

    def _target_path(self) -> Path:
        if self._daily_rollover:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
            filename = f"{self._prefix}_{stamp}.jsonl"
        else:
            filename = f"{self._prefix}.jsonl"
        return self._base_dir / filename

    def write(self, payload: Mapping[str, Any]) -> str:
        record = dict(payload)
        trace_id = str(record.get("id") or uuid.uuid4().hex)
        record.setdefault("id", trace_id)
        record.setdefault("time", datetime.now(timezone.utc).isoformat())
        target = self._target_path()
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # Observability is best-effort; never break the main flow.
            return trace_id
        return trace_id
