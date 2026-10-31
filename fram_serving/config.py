from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


def _env_flag_enabled(name: str) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    logging.getLogger(__name__).warning(
        "Invalid %s value %r; treating the profile as disabled",
        name,
        raw,
    )
    return False


def _default_domain_overrides() -> dict[str, dict[str, float]]:
    return {
        "roadmap": {
            "tau1": 0.7,
            "tau2": 0.45,
            "default_query_reads": 5.0,
            "lambda_tok": 0.001,
            "section_repeat_penalty": 0.85,
            "section_penalty_floor": 0.35,
        }
    }


def _default_task_overrides() -> dict[str, dict[str, float]]:
    return {
        "diary": {
            "tau1": 0.7,
            "tau2": 0.45,
            "default_query_reads": 4.0,
            "section_repeat_penalty": 0.9,
            "section_penalty_floor": 0.4,
        }
    }


def _default_time_sensitivity_task() -> dict[str, str]:
    return {
        "diary": "high",
        "qa": "medium",
    }


def _default_time_sensitivity_domain() -> dict[str, str]:
    return {
        "roadmap": "medium",
        "general": "medium",
    }


class PhaseDConfig(BaseModel):
    enabled: bool = False
    debug_observability: bool = False
    enable_memory_bridge: bool = False
    enable_memory_weighting: bool = True
    enable_alpha_color_weighting: bool = True
    enable_rarity_weighting: bool = True
    enable_recency_weighting: bool = True
    enable_affect_weighting: bool = True
    enable_coherence_weighting: bool = True
    enable_quality_weighting: bool = True
    # Priority scaling
    priority_clip_min: float = 0.0
    priority_clip_max: float = 2.0
    priority_normalize: bool = False
    # Graph priority
    enable_priority_graph: bool = True
    priority_graph_similarity_threshold: float = 0.6
    priority_graph_cluster_boost_weight: float = 0.25
    priority_graph_aggregation_mode: str = "mean"
    # Memory bridge priority
    enable_memory_bridge_priority: bool = True
    memory_bridge_priority_weight: float = 0.5
    # Temporal priority
    enable_temporal_priority: bool = False
    temporal_recency_weight: float = 0.0
    temporal_decay_half_life: float = 3.0
    temporal_min_floor: float = 0.2
    # Hysteresis (cross-session stability)
    enable_hysteresis: bool = False
    hysteresis_weight: float = 0.0
    # Inspector (diagnostic only)
    enable_priority_inspector: bool = False
    # Core Phase D scoring toggles
    enable_quaternions: bool = False
    enable_logistic_alpha: bool = False
    quat_proj_seed: int = 17
    logistic_r: float = 3.0
    logistic_t_max: int = 32
    logistic_state_reporting: bool = False


class FRAMConfig(BaseModel):
    # §19 Practical defaults
    # Routing & confidence
    k0: int = 32
    rank_min: int = 6
    rank_max: int = 12
    hot_rank_cap: int = 8
    alpha1: float = 0.01  # no-widen FN rate target
    alpha2: float = 0.003  # skip-global FN rate target
    G: int = 16  # global shortlist when conf < tau2

    # Anchors
    dr: int = 3
    step_s: tuple[float, float] = (0.7, 1.2)
    radial_pct: tuple[float, float] = (0.6, 0.9)
    alpha_div: float = 0.2
    light_probe_m: int = 8
    eps_gain: float = 1e-3
    celf_enabled: bool = True

    # Coverage
    gamma: float = 0.6
    u_max: int = 3
    eta_sparse_penalty: float = 0.4
    eta: float = 0.4
    section_repeat_penalty: float = 0.7
    section_penalty_floor: float = 0.3

    # Coverage (explicit knobs exposed to API/trace)
    coverage_gamma: float = 0.6
    coverage_u_max: int = 3

    # Budgets
    headroom: float = 0.15
    lambda_tok: float = 0.002
    lambda_rerank: float = 0.05
    pairs_scale: float = 1.0
    default_query_reads: int = 5
    embedding_dim: int = 1024
    embedding_backend: str = "vocab"

    session_memory_k: int = 2
    cognitive_memory_k: int = 12
    # 0 or less means "no cap" (breathing mode).
    cognitive_memory_token_budget: int = 0
    # 0 or less means unlimited cognitive memory slots (decoupled from read budget).
    cognitive_memory_slot_budget: int = 0
    cognitive_memory_trace_k: int = 3
    cognitive_memory_embedding_backend: str = "hashing"
    cognitive_memory_semantic_model: str = "all-MiniLM-L6-v2"
    # Blend factor for query-only recall when ranking episodes (0 disables the boost).
    cognitive_memory_query_recall_weight: float = 0.2
    # Recency-decay half-life for cognitive memory search ranking
    # (fram_serving/memory.py:_recency_weight). Was previously read via
    # getattr(self._config, "cognitive_memory_half_life_hours", 12.0) with no
    # matching FRAMConfig field to actually set it - i.e. permanently 12.0,
    # silently and unconfigurably, no matter what. Diagnosed 2026-07-22 as
    # the root cause of the 2026-01-21 conversation-memory eval's top1=0.000
    # collapse: a fixed historical benchmark's target episodes decayed under
    # this hardcoded 12h half-life until any fresher, barely-relevant
    # episode outranked them in every retrieval mode. See
    # docs/observability_2026-07-22-eval-anomaly.md.
    cognitive_memory_half_life_hours: float = 12.0
    cognitive_memory_max_segment_turns: int = 5000
    cognitive_memory_retain_segments: int | None = None
    cognitive_memory_retain_days: int | None = None
    preserve_full_experience: bool = True
    memory_capsule_enabled: bool = False
    memory_capsule_retrieval_enabled: bool = False
    memory_capsule_retrieval_k: int = 4
    memory_capsule_retrieval_turns_per_capsule: int = 2
    memory_capsule_retrieval_half_life_hours: float = 72.0
    # Durable lived-experience memory. Actual query/answer events, embeddings,
    # session lineage, higher-dimensional projections, and lifted fractal paths
    # are stored transactionally in SQLite and survive process restarts.
    lived_memory_enabled: bool = True
    lived_memory_target_dim: int = 12
    lived_memory_fractal_nodes: int = 64
    lived_memory_recall_k: int = 4
    lived_memory_scan_limit: int = 5000
    lived_memory_state_decay: float = 0.82
    lived_memory_busy_timeout_seconds: float = 5.0
    # Post-finalization, sanitized observability sidecar. It never participates
    # in retrieval, selection, reranking, or response generation.
    continuity_witness_enabled: bool = False
    continuity_witness_max_age_seconds: float = 3600.0
    continuity_witness_lock_timeout_seconds: float = 0.1
    working_memory_dedupe_window_sec: float = 2.0
    mcp_cognitive_write_enabled: bool = False

    # Cognitive memory tuning (optional)
    enable_cognitive_ann_bridge: bool = True
    cognitive_ann_top_k: int = 8
    cognitive_ann_weight: float = 1.0
    cognitive_ann_floor_boost: float = 0.01
    enable_retention_curve: bool = False
    retention_half_life_days: float = 30.0
    enable_decay: bool = False
    forgetting_half_life_days: float = 30.0
    enable_hard_forgetting: bool = False
    forgetting_threshold: float = 0.05
    hard_forgetting_mode: str = "dry_run"
    min_active_items: int = 0
    # Connectors / guardrails
    enable_connector_ingestion: bool = False
    connector_max_items: int = 50
    connector_refresh_seconds: int = 3600
    enable_guardrails: bool = False
    # Phase E (retention/decay placeholders)
    enable_retention_curve: bool = False
    enable_decay: bool = False
    retention_half_life_days: float = 30.0
    forgetting_half_life_days: float = 30.0
    enable_hard_forgetting: bool = False
    hard_forgetting_mode: str = "dry_run"
    forgetting_threshold: float = 0.05
    min_active_items: int = 100
    # Phase G (storage compaction/archival scaffolding)
    enable_storage_compaction: bool = False
    enable_archival: bool = False
    archive_criteria: dict[str, float] = Field(default_factory=dict)
    compaction_threshold_mb: float = 128.0
    max_archive_size_mb: float = 1024.0
    active_store_min_items: int = 100

    # Fractal routing (feature flag & knobs)
    fractal_enabled: bool = False
    fractal_scoring_mode: Literal["legacy", "source_frame"] = "legacy"
    fractal_blend_alpha: float = 0.4
    fractal_downsample_target: int = 256
    fractal_influence_enabled: bool = False
    fractal_influence_alpha: float = 0.05
    fractal_quat_influence: bool = False
    fractal_quat_weight: float = 0.2
    fractal_quat_use_lambda: bool = True

    # Recursive Rotational Lift capsule enrichment (feature flag & knobs).
    # Purely additive write-side experiment: populates memory_capsule's
    # self_invariants/open_residuals fields from the capsule's own trajectory
    # embeddings. Never affects retrieval/ranking. See docs/rotational_lift.md.
    rotational_lift_enabled: bool = False
    rotational_lift_invariant_components: int = 3
    rotational_lift_lift_hops: int = 2
    rotational_lift_reentry_epsilon: float = 0.25

    # Capsule session lineage (feature flag). Purely additive write-side
    # experiment: records a "continues" link from a capsule to the previous
    # capsule sharing the same session_id, and (only if rotational_lift is
    # also enabled) tags the first hop of that capsule's open_residuals
    # chain with the parent capsule's id. Never affects retrieval/ranking.
    capsule_session_lineage_enabled: bool = False
    # Hard cap on how many existing capsules the lineage lookup will scan
    # (newest-first) before giving up. Without this, an ever-growing
    # append-only capsule store would make every write's lineage lookup
    # slower as the store grows; 500 is a generous default for typical
    # session recency (a session's predecessor is normally near the front).
    capsule_session_lineage_scan_limit: int = 500
    # How many ancestor capsules (walked via each capsule's own recorded
    # "continues" link, not a store-wide scan) to fold into this capsule's
    # rotational-lift trajectory before lifting. 0 (default) preserves
    # today's behavior exactly - each capsule lifts only its own turns.
    # Requires both rotational_lift_enabled and capsule_session_lineage_enabled.
    rotational_lift_lineage_window: int = 0

    # PIL, the muscle-memory retriever (fram_serving/pil.py). First slice is
    # observability only: when enabled, a `pil_teach` block is attached to the
    # finished trace. It never changes selection, ranking, or memory writes.
    # Reconstruction from note 35 via docs/manual/08_reconstruction_kit.md.
    pil_enabled: bool = False
    pil_observe_only: bool = True

    # Phase D scaffolding (placeholders only)
    phase_d: PhaseDConfig = Field(default_factory=PhaseDConfig)

    # Query metadata defaults
    default_domain: str = "general"
    default_task: str = "qa"

    # Domain/task overrides
    domain_overrides: dict[str, dict[str, float]] = Field(
        default_factory=_default_domain_overrides
    )
    task_overrides: dict[str, dict[str, float]] = Field(
        default_factory=_default_task_overrides
    )
    time_sensitivity_task: dict[str, str] = Field(
        default_factory=_default_time_sensitivity_task
    )
    time_sensitivity_domain: dict[str, str] = Field(
        default_factory=_default_time_sensitivity_domain
    )
    negative_cue_cooldown_minutes: int = 10
    semantic_entity_graph: dict[str, list[str]] = Field(default_factory=lambda: {})
    semantic_reranker_model: str | None = None

    # Metrics window configuration
    metrics_window: int = 500

    # Layout
    theta_global: float = 0.7

    # Domain time-scale placeholder for freshness
    tau_domain_days: float = 30.0

    # Confidence thresholds (tau1 >= tau2)
    # If p >= tau1 -> local (no widening)
    # If tau2 <= p < tau1 -> anchors (second local probe)
    # If p < tau2 -> global (small global shortlist)
    tau1: float = 0.8
    tau2: float = 0.5

    # Storage (Task A)
    STORAGE_ROOT: Path = Path("./storage")
    STORAGE_SUBFOLDERS: dict[str, str] = {
        "corpus": "corpus",
        "index": "index",
        "claims": "claims",
        "versions": "versions",
        "traces": "traces",
        "backups": "backups",
        "observability": "observability",
        "memory": "memory",
        "visual": "visual_evidence",
    }

    # Connector API key (Task B)
    api_key: str = "dev-key"

    @property
    def lambda_tokens(self) -> float:
        return self.lambda_tok

    @property
    def use_celf(self) -> bool:
        return self.celf_enabled

    @classmethod
    def from_env(cls) -> "FRAMConfig":
        env_map: dict[str, tuple[str, ...]] = {
            "STORAGE_ROOT": ("FRAM_STORAGE_ROOT",),
            "coverage_gamma": ("FRAM_COVERAGE_GAMMA",),
            "coverage_u_max": ("FRAM_COVERAGE_U_MAX",),
            "lambda_tok": ("FRAM_LAMBDA_TOK", "FRAM_LAMBDA_TOKENS"),
            "lambda_rerank": ("FRAM_LAMBDA_RERANK",),
            "pairs_scale": ("FRAM_PAIRS_SCALE",),
            "celf_enabled": ("FRAM_CELF_ENABLED", "FRAM_USE_CELF"),
            "embedding_backend": ("FRAM_EMBEDDING_BACKEND",),
            "metrics_window": ("FRAM_METRICS_WINDOW",),
            "default_query_reads": ("FRAM_DEFAULT_QUERY_READS",),
            "section_repeat_penalty": ("FRAM_SECTION_REPEAT_PENALTY",),
            "section_penalty_floor": ("FRAM_SECTION_PENALTY_FLOOR",),
            "default_domain": ("FRAM_DEFAULT_DOMAIN",),
            "default_task": ("FRAM_DEFAULT_TASK",),
            "cognitive_memory_k": ("FRAM_COGNITIVE_MEMORY_K",),
            "cognitive_memory_token_budget": ("FRAM_COGNITIVE_MEMORY_TOKEN_BUDGET",),
            "cognitive_memory_slot_budget": ("FRAM_COGNITIVE_MEMORY_SLOT_BUDGET",),
            "cognitive_memory_trace_k": ("FRAM_COGNITIVE_MEMORY_TRACE_K",),
            "cognitive_memory_embedding_backend": (
                "FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND",
            ),
            "cognitive_memory_semantic_model": (
                "FRAM_COGNITIVE_MEMORY_SEMANTIC_MODEL",
            ),
            "cognitive_memory_query_recall_weight": (
                "FRAM_COGNITIVE_MEMORY_QUERY_RECALL_WEIGHT",
            ),
            "cognitive_memory_half_life_hours": (
                "FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS",
            ),
            "cognitive_memory_max_segment_turns": (
                "FRAM_COGNITIVE_MEMORY_MAX_SEGMENT_TURNS",
            ),
            "cognitive_memory_retain_segments": (
                "FRAM_COGNITIVE_MEMORY_RETAIN_SEGMENTS",
            ),
            "cognitive_memory_retain_days": ("FRAM_COGNITIVE_MEMORY_RETAIN_DAYS",),
            "preserve_full_experience": ("FRAM_PRESERVE_FULL_EXPERIENCE",),
            "mcp_cognitive_write_enabled": ("FRAM_MCP_COGNITIVE_WRITE_ENABLED",),
            "enable_cognitive_ann_bridge": ("FRAM_ENABLE_COGNITIVE_ANN_BRIDGE",),
            "cognitive_ann_top_k": ("FRAM_COGNITIVE_ANN_TOP_K",),
            "cognitive_ann_weight": ("FRAM_COGNITIVE_ANN_WEIGHT",),
            "cognitive_ann_floor_boost": ("FRAM_COGNITIVE_ANN_FLOOR_BOOST",),
            "enable_retention_curve": ("FRAM_ENABLE_RETENTION_CURVE",),
            "retention_half_life_days": ("FRAM_RETENTION_HALF_LIFE_DAYS",),
            "enable_decay": ("FRAM_ENABLE_DECAY",),
            "forgetting_half_life_days": ("FRAM_FORGETTING_HALF_LIFE_DAYS",),
            "enable_hard_forgetting": ("FRAM_ENABLE_HARD_FORGETTING",),
            "forgetting_threshold": ("FRAM_FORGETTING_THRESHOLD",),
            "hard_forgetting_mode": ("FRAM_HARD_FORGETTING_MODE",),
            "min_active_items": ("FRAM_MIN_ACTIVE_ITEMS",),
            "fractal_enabled": ("FRAM_FRACTAL_ENABLED",),
            "fractal_scoring_mode": ("FRAM_FRACTAL_SCORING_MODE",),
            "fractal_blend_alpha": ("FRAM_FRACTAL_BLEND_ALPHA",),
            "fractal_downsample_target": ("FRAM_FRACTAL_DOWNSAMPLE_TARGET",),
            "fractal_influence_enabled": ("FRAM_FRACTAL_INFLUENCE",),
            "fractal_influence_alpha": ("FRAM_FRACTAL_INFLUENCE_ALPHA",),
            "fractal_quat_influence": (
                "FRAM_FRACTAL_QUAT_INFLUENCE",
                "FRAM_FRACTAL_QUATERNION_INFLUENCE",
            ),
            "fractal_quat_weight": ("FRAM_FRACTAL_QUAT_WEIGHT",),
            "fractal_quat_use_lambda": ("FRAM_FRACTAL_QUAT_USE_LAMBDA",),
            "rotational_lift_enabled": ("FRAM_ROTATIONAL_LIFT_ENABLED",),
            "rotational_lift_invariant_components": (
                "FRAM_ROTATIONAL_LIFT_INVARIANT_COMPONENTS",
            ),
            "rotational_lift_lift_hops": ("FRAM_ROTATIONAL_LIFT_LIFT_HOPS",),
            "rotational_lift_reentry_epsilon": (
                "FRAM_ROTATIONAL_LIFT_REENTRY_EPSILON",
            ),
            "capsule_session_lineage_enabled": (
                "FRAM_CAPSULE_SESSION_LINEAGE_ENABLED",
            ),
            "capsule_session_lineage_scan_limit": (
                "FRAM_CAPSULE_SESSION_LINEAGE_SCAN_LIMIT",
            ),
            "rotational_lift_lineage_window": ("FRAM_ROTATIONAL_LIFT_LINEAGE_WINDOW",),
            "memory_capsule_enabled": ("FRAM_MEMORY_CAPSULE_ENABLED",),
            "memory_capsule_retrieval_enabled": (
                "FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED",
            ),
            "memory_capsule_retrieval_k": ("FRAM_MEMORY_CAPSULE_RETRIEVAL_K",),
            "memory_capsule_retrieval_turns_per_capsule": (
                "FRAM_MEMORY_CAPSULE_RETRIEVAL_TURNS_PER_CAPSULE",
            ),
            "memory_capsule_retrieval_half_life_hours": (
                "FRAM_MEMORY_CAPSULE_RETRIEVAL_HALF_LIFE_HOURS",
            ),
            "lived_memory_enabled": ("FRAM_LIVED_MEMORY_ENABLED",),
            "lived_memory_target_dim": ("FRAM_LIVED_MEMORY_TARGET_DIM",),
            "lived_memory_fractal_nodes": ("FRAM_LIVED_MEMORY_FRACTAL_NODES",),
            "lived_memory_recall_k": ("FRAM_LIVED_MEMORY_RECALL_K",),
            "lived_memory_scan_limit": ("FRAM_LIVED_MEMORY_SCAN_LIMIT",),
            "lived_memory_state_decay": ("FRAM_LIVED_MEMORY_STATE_DECAY",),
            "lived_memory_busy_timeout_seconds": (
                "FRAM_LIVED_MEMORY_BUSY_TIMEOUT_SECONDS",
            ),
            "continuity_witness_enabled": ("FRAM_CONTINUITY_WITNESS_ENABLED",),
            "continuity_witness_max_age_seconds": (
                "FRAM_CONTINUITY_WITNESS_MAX_AGE_SECONDS",
            ),
            "continuity_witness_lock_timeout_seconds": (
                "FRAM_CONTINUITY_WITNESS_LOCK_TIMEOUT_SECONDS",
            ),
            "working_memory_dedupe_window_sec": (
                "FRAM_WORKING_MEMORY_DEDUPE_WINDOW_SEC",
            ),
            "enable_connector_ingestion": ("FRAM_ENABLE_CONNECTOR_INGESTION",),
            "connector_max_items": ("FRAM_CONNECTOR_MAX_ITEMS",),
            "connector_refresh_seconds": ("FRAM_CONNECTOR_REFRESH_SECONDS",),
            "enable_guardrails": ("FRAM_ENABLE_GUARDRAILS",),
            "pil_enabled": ("FRAM_PIL_ENABLED",),
            "pil_observe_only": ("FRAM_PIL_OBSERVE_ONLY",),
            "enable_storage_compaction": ("FRAM_ENABLE_STORAGE_COMPACTION",),
            "enable_archival": ("FRAM_ENABLE_ARCHIVAL",),
            "compaction_threshold_mb": ("FRAM_COMPACTION_THRESHOLD_MB",),
            "max_archive_size_mb": ("FRAM_MAX_ARCHIVE_SIZE_MB",),
            "active_store_min_items": ("FRAM_ACTIVE_STORE_MIN_ITEMS",),
        }
        overrides: dict[str, Any] = {}
        for field, env_names in env_map.items():
            for env_name in env_names:
                raw = os.getenv(env_name)
                if raw is None:
                    continue
                try:
                    parsed = cls(**{field: raw})
                except ValidationError:
                    continue
                overrides[field] = getattr(parsed, field)
                break
        alpha_env = os.getenv("FRAM_FRACTAL_BLEND_ALPHA")
        if alpha_env is not None:
            try:
                overrides["fractal_blend_alpha"] = float(alpha_env)
            except ValueError:
                logging.getLogger(__name__).warning(
                    "Invalid FRAM_FRACTAL_BLEND_ALPHA '%s'; using default %.3f",
                    alpha_env,
                    cls().fractal_blend_alpha,
                )
        base = cls()
        # Optional dev profile: enable light cognitive seeding unless explicitly set
        if _env_flag_enabled("FRAM_DEV_PROFILE"):
            if "default_query_reads" not in overrides:
                try:
                    overrides["default_query_reads"] = int(5)
                except Exception:
                    pass
            if "cognitive_memory_k" not in overrides:
                try:
                    overrides["cognitive_memory_k"] = int(12)
                except Exception:
                    pass
            if "cognitive_memory_token_budget" not in overrides:
                try:
                    overrides["cognitive_memory_token_budget"] = int(0)
                except Exception:
                    pass
            if "fractal_enabled" not in overrides:
                overrides["fractal_enabled"] = True
        preserve_full_experience = overrides.get(
            "preserve_full_experience",
            base.preserve_full_experience,
        )
        if preserve_full_experience:
            overrides.update(
                {
                    "cognitive_memory_retain_segments": None,
                    "cognitive_memory_retain_days": None,
                    "enable_retention_curve": False,
                    "enable_decay": False,
                    "enable_hard_forgetting": False,
                }
            )
        if not overrides:
            return base
        return base.model_copy(update=overrides)
