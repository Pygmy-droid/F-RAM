# Phase D Priority Graph & Inspector

## Purpose

Blend scalar Phase D priority signals with lightweight cluster awareness and expose the results for diagnostics. All gates default to OFF; enabling them is opt-in.

## Components

- `phase_d_priority`: scalar blend of affect/coherence/quality/rarity/recency (neutral at 0.5), bounded by `priority_clip_min/max`.
- `graph_priority`: cluster-adjusted priority via similarity edges (`priority_graph_similarity_threshold`), aggregation (`mean`/`max`), and boost weight.
- `final_priority_for_bridge`: blended scalar + graph priority (plus optional temporal and hysteresis factors) used to sort cognitive seeds for the memory bridge.
- `priority_snapshot`: observability view of recent priorities, surfaced via `/observability/phase_d_memory` and the HTML inspector (`enable_priority_inspector`).

## Config (PhaseDConfig)

- `enable_priority_graph`, `priority_graph_similarity_threshold`, `priority_graph_cluster_boost_weight`, `priority_graph_aggregation_mode`
- `enable_memory_bridge_priority`, `memory_bridge_priority_weight`
- `enable_temporal_priority`, `temporal_recency_weight`, `temporal_decay_half_life`, `temporal_min_floor`
- `enable_hysteresis`, `hysteresis_weight`
- `priority_clip_min`, `priority_clip_max`, `priority_normalize`
- `enable_priority_inspector` (diagnostic only)

Defaults keep behavior unchanged unless explicitly enabled.

## Inspector

- `GET /observability/phase_d_memory?html=1` renders the inspector when `enable_priority_inspector` is true.
- Shows `phase_d_priority`, `graph_priority`, `final_priority`, `temporal_factor`, `hysteresis_boost`, and previous-session metadata.
- JSON payload always includes `priority_snapshot` for automation.
