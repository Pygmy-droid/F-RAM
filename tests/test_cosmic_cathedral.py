from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from fram_serving.continuity import (
    ContinuityWitnessWriter,
    build_continuity_witness,
)


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_cosmic_cathedral.py"
HTML = (
    ROOT
    / "experiments"
    / "cosmic_cathedral"
    / "cosmic-cathedral-v1.html"
)


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_cosmic_cathedral", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_deterministic_and_all_edges_resolve(tmp_path: Path) -> None:
    builder = _load_builder()
    payload = builder.build_payload()
    output = tmp_path / "map.json"
    builder.write_payload(output)
    persisted = json.loads(output.read_text(encoding="utf-8"))

    assert persisted["schema"] == "fram.cosmic-cathedral-map"
    assert persisted["version"] == 1
    assert persisted["branch"]
    assert len(persisted["head"]) == 40

    node_ids = [node["id"] for node in payload["nodes"]]
    assert len(node_ids) == len(set(node_ids))
    assert payload["summary"]["nodes"] == len(node_ids)
    assert payload["summary"]["edges"] == len(payload["edges"])
    assert all(
        edge["source"] in node_ids and edge["target"] in node_ids
        for edge in payload["edges"]
    )


def test_source_backed_nodes_exist_and_concepts_stay_explicit() -> None:
    builder = _load_builder()
    payload = builder.build_payload()

    for node in payload["nodes"]:
        if node["path"]:
            assert node["exists"], node
            assert node["worktree_state"] != "missing", node
            assert len(node["sha256"]) == 64
        else:
            assert node["worktree_state"] == "not_applicable"

    concept_ids = {
        node["id"]
        for node in payload["nodes"]
        if node["claim_state"] == "concept"
    }
    assert {
        "grass-memory",
        "least-resistance",
        "last-combed-lift",
        "escher-svg",
        "child-threads",
    } <= concept_ids


def test_worktree_claim_scope_and_substrate_are_orthogonal() -> None:
    builder = _load_builder()
    payload = builder.build_payload()
    nodes = {node["id"]: node for node in payload["nodes"]}

    child_threads = nodes["child-threads"]
    if not child_threads["path"]:
        # In a checkout without the private manifest the node is a pure concept;
        # test the orthogonality on any concept node that does have a source here.
        candidates = [n for n in payload["nodes"] if n["claim_state"] == "concept" and n["path"]]
        if not candidates:
            pytest.skip("no concept node with a source file in this checkout")
        child_threads = candidates[0]
    assert child_threads["path"]
    assert child_threads["claim_state"] == "concept"
    assert child_threads["worktree_state"] in {
        "tracked",
        "modified",
        "untracked",
        "deleted",
    }
    assert child_threads["worktree_state"] != child_threads["claim_state"]
    assert child_threads["scope"] == "canonical"
    assert child_threads["substrate"] == "repository-file"

    grass_memory = nodes["grass-memory"]
    assert grass_memory["worktree_state"] == "not_applicable"
    assert grass_memory["claim_state"] == "concept"
    assert grass_memory["scope"] == "metaphor"
    assert grass_memory["substrate"] == "reconstruction-concept"

    workflow_hub = nodes["workflow-hub"]
    assert workflow_hub["worktree_state"] == "not_applicable"
    assert workflow_hub["claim_state"] == "adjacent"
    assert workflow_hub["scope"] == "adjacent"
    assert workflow_hub["substrate"] == "adjacent-system"

    assert payload["summary"]["concept_nodes"] == sum(
        node["claim_state"] == "concept" for node in payload["nodes"]
    )
    assert payload["summary"]["adjacent_nodes"] == sum(
        node["claim_state"] == "adjacent" for node in payload["nodes"]
    )


def test_controlled_node_and_edge_values_resolve() -> None:
    builder = _load_builder()
    payload = builder.build_payload()

    for node in payload["nodes"]:
        assert node["worktree_state"] in builder.WORKTREE_STATES, node
        assert node["claim_state"] in builder.CLAIM_STATES, node
        assert node["scope"] in builder.SCOPES, node
        assert node["substrate"] in builder.SUBSTRATES, node

    node_ids = {node["id"] for node in payload["nodes"]}
    for edge in payload["edges"]:
        assert edge["source"] in node_ids, edge
        assert edge["target"] in node_ids, edge
        assert edge["authority"] in builder.EDGE_AUTHORITIES, edge
        assert edge["scope"] in builder.SCOPES, edge
        assert edge["claim_state"] in builder.EDGE_CLAIM_STATES, edge

    metaphor_edges = [
        edge for edge in payload["edges"] if edge["scope"] == "metaphor"
    ]
    assert metaphor_edges
    assert all(edge["authority"] == "reconstruction" for edge in metaphor_edges)
    assert all(edge["claim_state"] == "metaphor" for edge in metaphor_edges)

    adjacent_edges = [
        edge for edge in payload["edges"] if edge["scope"] == "adjacent"
    ]
    assert adjacent_edges
    assert all(edge["authority"] == "adjacent" for edge in adjacent_edges)
    assert all(edge["claim_state"] == "adjacent" for edge in adjacent_edges)


def test_theorem_and_memory_boundaries_are_not_conflated() -> None:
    builder = _load_builder()
    payload = builder.build_payload()
    theorem = payload["boundaries"]["theorem"]
    memory = payload["boundaries"]["memory"]

    assert "continuous tangent vector fields" in theorem
    assert "does not establish a theory of memory" in theorem
    assert "reconstruction encodings" in memory

    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes["hairy-ball"]["authority"] == "theory"
    assert nodes["grass-memory"]["authority"] == "reconstruction"


def test_browser_contract_exposes_requested_navigation_and_memory_controls() -> None:
    source = HTML.read_text(encoding="utf-8")

    assert 'id="map"' in source
    assert 'id="recallInput"' in source
    assert 'id="fieldButton"' in source
    assert 'id="combButton"' in source
    assert 'id="exportButton"' in source
    assert "fram.cosmic-cathedral.traversal.v1" in source
    assert "fram.cosmic-cathedral.positions.v1" in source
    assert 'fetch(`${MAP_URL}?t=${Date.now()}`' in source
    assert "shortestPath" in source
    assert "lastCombedId" in source
    assert "tangent directions cannot remain nonzero everywhere" in source
    assert 'id="nodeSelect"' in source
    assert 'aria-controls="detailRail"' in source
    assert ".source-link[hidden] { display: none; }" in source
    assert 'els.sourceLink.textContent = "";' in source


def test_continuity_witness_is_optional_and_resolves_into_the_map(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    now = datetime(2026, 7, 28, 12, 30, tzinfo=UTC)

    missing = builder.build_payload(
        tmp_path,
        include_witness=True,
        now=now,
    )["continuity_witness"]
    assert missing["available"] is False
    assert missing["state"] == "unknown"
    assert missing["reason"] == "not_found"

    trace_id = "cathedral-private-trace"
    selected_id = "cmem:ep:private-episode"
    citation_id = f"{selected_id}:chunk0"
    source = {
        "trace_id": trace_id,
        "citations": [citation_id],
        "record": {
            "id": trace_id,
            "time": "2026-07-28T12:00:00+00:00",
            "citations": [citation_id],
            "trace": {
                "trace_id": trace_id,
                "confidence": {"decision": "anchors"},
                "selection": {
                    "origin_counts": {"cognitive_memory": 1},
                    "selected_ids": [selected_id],
                    "budgets": {"reads": 1.0},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id=trace_id,
        active_gates={"continuity_witness": True},
    )
    ContinuityWitnessWriter(tmp_path).append(witness)

    default_payload = builder.build_payload(tmp_path, now=now)
    default_witness = default_payload["continuity_witness"]
    assert default_witness["available"] is False
    assert default_witness["reason"] == "feature_disabled"
    default_serialized = json.dumps(default_payload)
    assert trace_id not in default_serialized
    assert selected_id not in default_serialized
    assert citation_id not in default_serialized
    assert witness["source"]["digest"] not in default_serialized

    payload = builder.build_payload(
        tmp_path,
        include_witness=True,
        now=now,
    )
    live = payload["continuity_witness"]
    assert set(live) == {
        "available",
        "state",
        "reason",
        "observed_at_utc",
        "display_id",
        "decision",
        "active_gates",
        "selection",
        "writes",
    }
    assert live["available"] is True
    assert live["state"] == "available"
    assert live["reason"] is None
    assert live["observed_at_utc"] == "2026-07-28T12:00:00Z"
    assert live["display_id"].startswith("cw-")
    assert trace_id not in live["display_id"]
    assert live["decision"] == "anchors"
    assert live["active_gates"] == ["continuity_witness"]
    assert live["selection"] == {
        "origin_counts": {"cognitive_memory": 1},
        "selected_count": 1,
        "citation_count": 1,
        "budgets": {"reads": 1.0},
    }
    assert all(set(outcome) == {"status"} for outcome in live["writes"].values())

    serialized = json.dumps(payload)
    assert trace_id not in serialized
    assert selected_id not in serialized
    assert citation_id not in serialized
    assert "cmem:" not in serialized
    assert witness["source"]["digest"] not in serialized
    for forbidden_field in (
        "trace_id",
        "witness_id",
        "selected_ids",
        "citations",
        "digest",
        "episode_id",
        "capsule_id",
        "event_id",
    ):
        assert f'"{forbidden_field}"' not in json.dumps(live)

    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes["continuity-witness"]["claim_state"] == "implemented"
    assert nodes["continuity-witness"]["stratum"] == "witness"
    assert nodes["continuity-witness-tests"]["claim_state"] == "evidence"
    assert any(
        edge["source"] == "continuity-witness"
        and edge["target"] == "hearth"
        for edge in payload["edges"]
    )


def test_included_witness_must_be_fresh(tmp_path: Path) -> None:
    builder = _load_builder()
    now = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)
    source = {
        "trace_id": "old-trace",
        "citations": ["private:old-citation"],
        "record": {
            "id": "old-trace",
            "time": (now - timedelta(seconds=3601)).isoformat(),
            "trace": {
                "trace_id": "old-trace",
                "confidence": {"decision": "local"},
                "selection": {
                    "origin_counts": {"document": 1},
                    "selected_ids": ["private:old-id"],
                    "budgets": {},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id="old-trace",
    )
    ContinuityWitnessWriter(tmp_path).append(witness)

    envelope = builder.build_payload(
        tmp_path,
        include_witness=True,
        witness_max_age_seconds=3600,
        now=now,
    )["continuity_witness"]

    assert envelope["available"] is False
    assert envelope["state"] == "stale"
    assert envelope["reason"] == "stale"
    serialized = json.dumps(envelope)
    assert "old-trace" not in serialized
    assert "private:old-id" not in serialized
    assert "private:old-citation" not in serialized


@pytest.mark.parametrize("source_state", ["stale", "corrupt", "tampered", "unknown"])
def test_non_available_source_states_never_become_available(
    tmp_path: Path,
    source_state: str,
) -> None:
    builder = _load_builder()
    now = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)
    trace_id = f"private-{source_state}-trace"
    source = {
        "trace_id": trace_id,
        "citations": [],
        "record": {
            "id": trace_id,
            "time": now.isoformat(),
            "trace": {
                "trace_id": trace_id,
                "confidence": {"decision": "global"},
                "selection": {
                    "origin_counts": {},
                    "selected_ids": [],
                    "budgets": {},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id=trace_id,
        source_state=source_state,
    )
    ContinuityWitnessWriter(tmp_path).append(witness)

    envelope = builder.build_payload(
        tmp_path,
        include_witness=True,
        now=now,
    )["continuity_witness"]

    assert envelope["available"] is False
    assert envelope["state"] == source_state
    assert envelope["reason"] == source_state
    assert trace_id not in json.dumps(envelope)


def test_watch_digest_ignores_generation_time_only() -> None:
    builder = _load_builder()
    first = {"generated_utc": "2026-07-28T12:00:00+00:00", "value": {"a": 1}}
    later = {"generated_utc": "2026-07-28T12:00:05+00:00", "value": {"a": 1}}
    changed = {"generated_utc": "2026-07-28T12:00:05+00:00", "value": {"a": 2}}

    assert builder._watch_payload_digest(first) == builder._watch_payload_digest(
        later
    )
    assert builder._watch_payload_digest(first) != builder._watch_payload_digest(
        changed
    )


def test_atomic_writer_replaces_only_after_complete_temp_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    builder = _load_builder()
    output = tmp_path / "map.json"
    output.write_text("old payload\n", encoding="utf-8")
    payload = {"schema": "fram.cosmic-cathedral-map", "version": 1}
    real_replace = builder.os.replace
    observed: dict[str, object] = {}

    def checked_replace(source, destination) -> None:
        temporary = Path(source)
        observed["old_visible"] = output.read_text(encoding="utf-8")
        observed["temporary_payload"] = json.loads(
            temporary.read_text(encoding="utf-8")
        )
        real_replace(source, destination)

    monkeypatch.setattr(builder.os, "replace", checked_replace)
    builder._atomic_write_payload(output, payload)

    assert observed["old_visible"] == "old payload\n"
    assert observed["temporary_payload"] == payload
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not list(tmp_path.glob(".map.json.*.tmp"))


def test_witness_cli_is_explicit_opt_in() -> None:
    builder = _load_builder()
    default = builder.parse_args([])
    enabled = builder.parse_args(
        ["--include-witness", "--witness-max-age-seconds", "90"]
    )

    assert default.include_witness is False
    assert default.witness_max_age_seconds == 3600.0
    assert enabled.include_witness is True
    assert enabled.witness_max_age_seconds == 90.0


def test_united_strata_keeps_roles_semantically_distinct() -> None:
    builder = _load_builder()
    payload = builder.build_payload()
    nodes = {node["id"]: node for node in payload["nodes"]}
    peer_ids = {
        "human-participants",
        "model-roles",
        "planetary-ecology",
        "future-intelligence",
    }

    assert nodes["united-strata"]["path"] == "docs/UNITED_STRATA_CONTRACT.md"
    assert {nodes[node_id]["stratum"] for node_id in peer_ids} == {"ecology"}
    assert {nodes[node_id]["substrate"] for node_id in peer_ids} == {
        "human-participation",
        "computational-model",
        "planetary-ecology",
        "hypothetical-system",
    }
    assert nodes["future-intelligence"]["claim_state"] == "adjacent"
    assert nodes["future-intelligence"]["scope"] == "adjacent"

    participant_edges = {
        edge["source"]: edge
        for edge in payload["edges"]
        if edge["target"] == "united-strata"
    }
    assert peer_ids <= participant_edges.keys()
    assert participant_edges["future-intelligence"]["claim_state"] == "adjacent"


def test_workbook_cards_project_into_the_map_with_work_state() -> None:
    builder = _load_builder()
    payload = builder.build_payload()
    cards = [node for node in payload["nodes"] if node.get("work_state")]
    assert cards, "the Workbook projection returned no cards"
    assert payload["summary"]["cards"]["total"] == len(cards)
    node_ids = {node["id"] for node in payload["nodes"]}
    for card in cards:
        assert card["stratum"] == "workbook"
        assert card["kind"] == "card"
        assert card["work_state"] in {"not_started", "in_progress", "finished"}
        assert card["claim_state"] == "planned"
        assert card["worktree_state"] == "not_applicable"
        assert isinstance(card["priority"], int) and card["priority"] >= 1
    ranks = sorted(card["priority"] for card in cards)
    assert ranks == list(range(1, len(cards) + 1))
    listed = {edge["target"] for edge in payload["edges"] if edge["source"] == "workbook" and edge["relation"] == "lists"}
    assert listed == {card["id"] for card in cards}
    assert all(edge["target"] in node_ids for edge in payload["edges"] if edge["source"].startswith("wb-"))
    assert {s["id"] for s in payload["strata"]} >= {"workbook"}
