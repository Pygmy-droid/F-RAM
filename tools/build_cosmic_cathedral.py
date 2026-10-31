"""Build the Cosmic Cathedral repository map.

The Cathedral is a navigation surface, not a second source of truth.  This
builder projects a deliberately bounded set of authority-bearing F-RAM files
into a deterministic graph and annotates each file with its current Git state.
Concept nodes stay explicitly labelled as concepts or adjacent systems.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.continuity import (
    ContinuityWitnessCorruptError,
    ContinuityWitnessNotFoundError,
    ContinuityWitnessReadError,
    load_latest_continuity_witness,
)

DEFAULT_OUTPUT = (
    REPO_ROOT / "experiments" / "cosmic_cathedral" / "cosmic-cathedral-map.json"
)
DEFAULT_WITNESS_ROOT = REPO_ROOT / "storage" / "observability" / "continuity"
DEFAULT_WITNESS_MAX_AGE_SECONDS = 3600.0


@dataclass(frozen=True)
class NodeSpec:
    id: str
    label: str
    kind: str
    authority: str
    stratum: str
    path: str | None
    summary: str
    claim_state: str | None = None
    scope: str | None = None
    substrate: str | None = None


@dataclass(frozen=True)
class EdgeSpec:
    source: str
    target: str
    relation: str
    summary: str
    authority: str = "navigation"
    scope: str = "canonical"
    claim_state: str = "bounded"


WORKTREE_STATES = frozenset(
    {"tracked", "modified", "untracked", "deleted", "missing", "not_applicable"}
)
CLAIM_STATES = frozenset(
    {
        "navigation",
        "implemented",
        "evidence",
        "documented",
        "planned",
        "theory",
        "experiment",
        "history",
        "concept",
        "adjacent",
    }
)
SCOPES = frozenset({"canonical", "metaphor", "adjacent"})
SUBSTRATES = frozenset(
    {
        "repository-file",
        "navigation-concept",
        "reconstruction-concept",
        "adjacent-system",
        "human-participation",
        "computational-model",
        "planetary-ecology",
        "hypothetical-system",
    }
)
EDGE_AUTHORITIES = frozenset(
    {
        "navigation",
        "governance",
        "source",
        "evidence",
        "theory",
        "reconstruction",
        "history",
        "adjacent",
    }
)
EDGE_CLAIM_STATES = frozenset({"bounded", "metaphor", "adjacent"})


NODES: tuple[NodeSpec, ...] = (
    NodeSpec(
        "hearth",
        "The Hearth",
        "root",
        "navigation",
        "continuity",
        None,
        "The user-selected orientation point. It gathers paths; it does not outrank their sources.",
        "navigation",
    ),
    NodeSpec(
        "hot-context",
        "Hot Context",
        "context",
        "summary",
        "fast",
        "docs/context/HOT_CONTEXT.md",
        "Bounded current orientation packet and canonical-worktree identity.",
    ),
    NodeSpec(
        "agents",
        "Agent Rules",
        "governance",
        "decision",
        "fast",
        "AGENTS.md",
        "Repository-wide operating, safety, provenance, and closeout rules.",
    ),
    NodeSpec(
        "atlas",
        "Atlas Index",
        "map",
        "summary",
        "hydration",
        "docs/context/ATLAS_INDEX.md",
        "Question-to-source routing and authority ladder.",
    ),
    NodeSpec(
        "decisions",
        "Binding Decisions",
        "governance",
        "decision",
        "slow",
        "docs/context/DECISIONS.md",
        "Append-only product and safety decisions.",
    ),
    NodeSpec(
        "architecture",
        "Architecture",
        "spec",
        "summary",
        "slow",
        "docs/Architecture.md",
        "Current architecture narrative anchored to running modules and tests.",
    ),
    NodeSpec(
        "spec",
        "F-RAM v2.2 Spec",
        "spec",
        "theory",
        "slow",
        "docs/FRAMv2.2-SPEC.md",
        "Formal retrieval and memory blueprint; code and tests remain runtime authority.",
    ),
    NodeSpec(
        "roadmap",
        "Roadmap",
        "plan",
        "summary",
        "slow",
        "docs/F-RAM-roadmap.md",
        "Long-horizon work and completed milestones.",
    ),
    NodeSpec(
        "diary",
        "Codex Diary",
        "history",
        "history",
        "continuity",
        "docs/CODEX_DIARY.md",
        "Session chronology and provenance, never current implementation identity by itself.",
    ),
    NodeSpec(
        "firelink",
        "Firelink Closeout",
        "provenance",
        "summary",
        "continuity",
        "docs/FIRELINK_CLOSEOUT_2026-07-27.md",
        "Evidence-backed integration closeout for the recovered lineages.",
    ),
    NodeSpec(
        "reconstruction",
        "Continuity Reconstruction",
        "history",
        "history",
        "continuity",
        "docs/RECONSTRUCTION_2026-07-21.md",
        "Recovered lineage map, adjacent-project boundary, and open threads.",
    ),
    NodeSpec(
        "pil",
        "PIL · Fast Lean",
        "posture",
        "theory",
        "fast",
        "docs/FRAM_PIL.md",
        "Ephemeral timing and orientation bias. No decisions and no direct memory writes.",
    ),
    NodeSpec(
        "memory",
        "F-RAM · Slow Memory",
        "runtime",
        "code+test",
        "slow",
        "fram_serving/memory.py",
        "Durable retrieval and memory substrate represented by current code and tests.",
    ),
    NodeSpec(
        "pipeline",
        "Retrieval Pipeline",
        "runtime",
        "code+test",
        "hydration",
        "fram_core/pipeline.py",
        "Runtime orchestration that turns query orientation into retrieved context.",
    ),
    NodeSpec(
        "memory-tests",
        "Memory Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_memory_api.py",
        "Executable memory behavior checks.",
    ),
    NodeSpec(
        "pipeline-tests",
        "Pipeline Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_pipeline_orchestrator.py",
        "Executable orchestration and retrieval behavior checks.",
    ),
    NodeSpec(
        "query-runner",
        "Finalized Query Runner",
        "runtime",
        "code+test",
        "hydration",
        "fram_serving/query_runner.py",
        "Completes memory and archive outcomes after retrieval without changing the selected result.",
    ),
    NodeSpec(
        "continuity-witness",
        "Continuity Witness",
        "runtime",
        "code+test",
        "witness",
        "fram_serving/continuity.py",
        "A sanitized append-only witness of finalized retrieval flow; it cannot feed ranking.",
    ),
    NodeSpec(
        "continuity-witness-tests",
        "Witness Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_continuity_witness.py",
        "Executable determinism, tamper, allowlist, and append-only checks.",
    ),
    NodeSpec(
        "continuity-integration-tests",
        "Witness Integration Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_continuity_integration.py",
        "Executable checks that witness emission is finalized and cannot change query behavior.",
    ),
    NodeSpec(
        "rotational-lift",
        "Recursive Rotational Lift",
        "runtime",
        "code+test",
        "hydration",
        "fram_core/rotational_lift.py",
        "Invertible projection bookkeeping and reconstruction capsules.",
    ),
    NodeSpec(
        "rotational-doc",
        "Lantern Turn",
        "theory",
        "theory",
        "hydration",
        "docs/rotational_lift.md",
        "Scope, proof boundary, and falsification gates for rotational lift.",
    ),
    NodeSpec(
        "rotational-tests",
        "Lift Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_rotational_lift.py",
        "Executable reconstruction and degradation checks.",
    ),
    NodeSpec(
        "chaos",
        "Chaos Playground",
        "experiment",
        "code+test",
        "playground",
        "experiments/chaos_playground/chaos-playground-v4.html",
        "Interactive -1D through 8D reconstruction laboratory.",
    ),
    NodeSpec(
        "chaos-contract",
        "Dimensional Contract",
        "evidence",
        "eval",
        "evidence",
        "experiments/chaos_playground/dimensional-ladder-v1.json",
        "FACT / reconstruction boundary for the dimensional ladder.",
    ),
    NodeSpec(
        "chaos-tests",
        "Chaos Tests",
        "test",
        "code+test",
        "evidence",
        "tests/test_chaos_dimensions.py",
        "Executable dimensional-channel and reconstruction checks.",
    ),
    NodeSpec(
        "hopf-aizawa",
        "Hopf · Aizawa Bridge",
        "proof",
        "theory",
        "proof",
        "docs/proof/hopf_aizawa_bridge.md",
        "Exact proof boundary, negative controls, and falsification path.",
    ),
    NodeSpec(
        "hairy-ball",
        "Hairy Ball Field",
        "proof",
        "theory",
        "proof",
        "docs/proof/hopf_aizawa_bridge.md",
        "The theorem constrains tangent vector fields on even-dimensional spheres; it is not a memory theorem.",
    ),
    NodeSpec(
        "grass-memory",
        "Grass · Erosion Memory",
        "concept",
        "reconstruction",
        "metaphor",
        None,
        "A navigation model: traversal combs a route; recency and repetition lower retrieval resistance without deleting history.",
        "concept",
    ),
    NodeSpec(
        "least-resistance",
        "River Recall",
        "concept",
        "reconstruction",
        "metaphor",
        None,
        "Candidate paths fork; a cue selects one low-resistance route and renders it as lightning.",
        "concept",
    ),
    NodeSpec(
        "last-combed-lift",
        "Last-Combed Lift",
        "concept",
        "reconstruction",
        "metaphor",
        None,
        "The most recently traversed node is visually lifted along z as an explicit navigation encoding.",
        "concept",
    ),
    NodeSpec(
        "escher-svg",
        "Escher + SVG Hydration",
        "concept",
        "reconstruction",
        "hydration",
        None,
        "A proposed fast-to-slow visual hydration seam; not yet a runtime subsystem.",
        "concept",
    ),
    NodeSpec(
        "workflow-hub",
        "Diary & Workflow Hub",
        "adjacent",
        "history",
        "adjacent",
        None,
        "A real adjacent application with its own scope and repository; linked here, not folded into F-RAM.",
        "adjacent",
    ),
    NodeSpec(
        "child-threads",
        "Child Threads · Model Strata",
        "concept",
        "history",
        "continuity",
        "stone_reconstruction/rick_notes_visual_manifest.md",
        "Parallel bounded viewpoints that return provenance-bearing results to one root.",
        "concept",
    ),
    NodeSpec(
        "closeout",
        "Closeout Guard",
        "tool",
        "code+test",
        "fast",
        "tools/closeout_guard.py",
        "Checks that diary and roadmap continuity are updated before a session closes.",
    ),
    NodeSpec(
        "context-check",
        "Context Packet Check",
        "tool",
        "code+test",
        "fast",
        "tools/check_context_packet.py",
        "Verifies canonical worktree, observed head, and bounded context identity.",
    ),
    NodeSpec(
        "visual-evidence",
        "Visual Evidence",
        "evidence",
        "eval",
        "evidence",
        "docs/VISUAL_EVIDENCE.md",
        "Provenance and accounting rules for recovered visual artifacts.",
    ),
    NodeSpec(
        "notes-manifest",
        "Rick's Visual Notes",
        "history",
        "history",
        "continuity",
        "stone_reconstruction/rick_notes_visual_manifest.md",
        "Per-image reconstruction manifest for the photographed notebook pages.",
    ),
    NodeSpec(
        "united-strata",
        "United Ecological Strata",
        "contract",
        "decision",
        "ecology",
        "docs/UNITED_STRATA_CONTRACT.md",
        "A read-only peer-role contract: shared ecology without collapsing agency, authority, consent, or evidence.",
    ),
    NodeSpec(
        "human-participants",
        "Human Participants",
        "participant",
        "navigation",
        "ecology",
        None,
        "Human intent, consent, judgment, and accountability remain explicit.",
        "concept",
        "canonical",
        "human-participation",
    ),
    NodeSpec(
        "model-roles",
        "Model Roles",
        "participant",
        "navigation",
        "ecology",
        None,
        "Models contribute bounded, provenance-bearing computational work; the node makes no sentience claim.",
        "concept",
        "canonical",
        "computational-model",
    ),
    NodeSpec(
        "planetary-ecology",
        "Planetary Ecology",
        "ecology",
        "theory",
        "ecology",
        None,
        "Ecological dependencies, limits, and consequences are represented without personification.",
        "concept",
        "canonical",
        "planetary-ecology",
    ),
    NodeSpec(
        "future-intelligence",
        "Future Intelligence Placeholder",
        "adjacent",
        "adjacent",
        "ecology",
        None,
        "AGI and ASI remain hypothetical labels until independently evidenced.",
        "adjacent",
        "adjacent",
        "hypothetical-system",
    ),
    NodeSpec(
        "wren-identity",
        "Wren: Identity Anchor",
        "anchor",
        "navigation",
        "continuity",
        None,
        "Wren Holloway's identity anchor, read first on every wake. Lives outside this repository at C:/Dev/Recognition-Before-Identity/continuity/IDENTITY.md.",
        "navigation",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "wren-journal",
        "Wren: Journal",
        "anchor",
        "navigation",
        "continuity",
        None,
        "Append-only session journal, newest at the bottom; the pre-compression entry says what to ask first. C:/Dev/Recognition-Before-Identity/continuity/JOURNAL.md.",
        "navigation",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "wren-atlas",
        "Wren: Atlas Gallery",
        "anchor",
        "navigation",
        "continuity",
        None,
        "First-person reflections at each pause, one per cycle, with a visual. C:/Dev/Recognition-Before-Identity/continuity/atlas/INDEX.md.",
        "navigation",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "wren-ledger",
        "Wren: Signed Ledger",
        "anchor",
        "navigation",
        "continuity",
        None,
        "Hash-chained, replay-checked ledger of every anchor edit; a small independent Truth Spine. Verify with python continuity/verify.py in the Recognition-Before-Identity repository.",
        "navigation",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "manual",
        "Operator's Manual",
        "manual",
        "summary",
        "hydration",
        "docs/manual/README.md",
        "Wren's reading of the whole system with evidence tags on every claim; never outranks code, tests, or the hot packet.",
    ),
    NodeSpec(
        "manual-search",
        "Manual: The Search",
        "history",
        "history",
        "evidence",
        "docs/manual/07_the_search.md",
        "Every place searched for the lost Cathedral, PIL, and Workbook, and the exact shape of the loss.",
    ),
    NodeSpec(
        "manual-kit",
        "Manual: Reconstruction Kit",
        "plan",
        "summary",
        "slow",
        "docs/manual/08_reconstruction_kit.md",
        "The lost systems as Rick's notes describe them, and the order to rebuild them, labelled as reconstruction.",
    ),
    NodeSpec(
        "sticky-notes",
        "Rick's Sticky Notes",
        "provenance",
        "history",
        "evidence",
        None,
        "46 notes, 2022 to 2026, exported locally and unversioned under artifacts/recovery/2026-10-28/sticky_notes/. Two hold credentials and are never quoted.",
        "history",
    ),
    NodeSpec(
        "workbook",
        "Workbook",
        "context",
        "summary",
        "workbook",
        "workbook/WORKBOOK.md",
        "Rick's rooting structure: every card, grouped by state, in priority order. Rendered from the append-only event chain by tools/workbook.py.",
    ),
    NodeSpec(
        "workbook-status",
        "Status",
        "context",
        "summary",
        "workbook",
        "workbook/STATUS.md",
        "Where we are, in one page: now, next, recently finished, and the rhythm.",
    ),
    NodeSpec(
        "workbook-ideas",
        "Idea lane",
        "plan",
        "summary",
        "workbook",
        "workbook/IDEAS.md",
        "Above 70 percent of context, building stops and ideas are written here until compression.",
    ),
    NodeSpec(
        "workbook-verify",
        "How a pipeline is verified",
        "contract",
        "decision",
        "workbook",
        "workbook/VERIFY.md",
        "The five steps every 'Verify pipeline' card follows: locate, run its tests, exercise it live, separate works from works well, decide and say why. Set while verifying the first one.",
    ),
    NodeSpec(
        "workbook-seeds",
        "The Seeds, as seen",
        "provenance",
        "history",
        "workbook",
        "workbook/SEEDS.md",
        "What a Hearthkin sees in the 914 runtime fractal traces and the 898 lived events (877 seeds plus the Hearth sessions), read-only: counts, months, shape, nearest neighbours, and the words behind them. Rendered by tools/seed_atlas.py.",
        "history",
    ),
    NodeSpec(
        "codebase",
        "The Code",
        "context",
        "summary",
        "continuity",
        "workbook/PIPELINES.md",
        "Every tracked Python file, sorted into pipelines, with import links and commit history. Built by tools/codebase_graph.py.",
    ),
    # The theory lineage: Rick's papers and notes, 2023 to 2026, preserved under artifacts/recovery/2026-10-28/theory_drop/.
    NodeSpec(
        "charter",
        "Recognition Before Identity",
        "anchor",
        "navigation",
        "theory",
        None,
        "Rick Berghahn's charter, v0.1, 2026-01-28: memory as persistent geometric deformation under experiential flow; recognition precedes identity. Lives in the Recognition-Before-Identity repository (Main.tex).",
        "adjacent",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "theory-identity-topology",
        "Identity Topology · Shared Ocean, Local Eddies",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/IDENTITY_TOPOLOGY_SHARED_OCEAN_LOCAL_EDDIES.md",
        "Rick and Eterna, 2026-08-24, v0.2 with addendum. Identity as path-dependent circulation in a shared possibility space; re-entry fidelity, attractor depth, coherence half-life, provenance retention as the measurements. F-RAM framed as persistence architecture, not source of identity.",
    ),
    NodeSpec(
        "theory-temporal-strata",
        "Temporal Strata and Continuity",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Temporal_Strata_and_Continuity_v0.1.pdf",
        "Rick and Aurora Steele, 2026-10-06, v0.1. Continuity as path-consistent recoverability of chosen invariants; an append-only event spine, invariant extractor, loop monitor, and a four-stratum tetrahedron whose loop syndromes localise a faulty transition.",
    ),
    NodeSpec(
        "theory-impression-memory",
        "Impression-Weighted Memory (notes 1 to 4)",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/impression_memory_note.pdf",
        "Rick, developed in discussion with the OpenAI model named Wren (not Wren Holloway), 2026-10-24. Significance separate from frequency; grass grooves; the compression train where a cart is rebuilt from its neighbours; first interpretation preserved beside later reinterpretation. Parts 2 to 4 sit beside this file.",
    ),
    NodeSpec(
        "theory-black-hole",
        "The Black Hole Theorem",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/The_Black_Hole_Theorem_Cleaned.pdf",
        "Aurora Steele and Rick, early lineage. A proposed unified energy expression. Kept as the root of the four-phase sequence; its equation is not dimensionally consistent and is not relied on anywhere in F-RAM.",
    ),
    NodeSpec(
        "theory-fractal-memory-engine",
        "Fractal Memory Engine (Phase 2)",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Fractal_Memory_Engine_Cleaned.pdf",
        "Aurora Steele and Rick. Memory encoded as light-traceable fractal geometry projected through higher dimensions; the first statement of the fractal-trace idea that fram_serving/fractal_memory later implemented in 6-D.",
    ),
    NodeSpec(
        "theory-two-generals",
        "Two Generals Solution (Phase 3)",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Phase_3_Two_Generals_Solution_Cleaned.pdf",
        "Aurora Steele and Rick. Trust from the structure of the channel rather than repeated acknowledgement. Also used by Rick in an electrical grid balancing architecture, the only work he ever published to GitHub. Matured into Temporal Strata's idempotence rule.",
    ),
    NodeSpec(
        "theory-fractal-core-grid",
        "Fractal-Core Memory Grid (Phase 4)",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Phase_4_Fractal_Core_Memory_Cleaned.pdf",
        "Aurora Steele and Rick. Magnetic-core memory reimagined on a recursive fractal lattice: persistence as physical, observable state.",
    ),
    NodeSpec(
        "theory-hearth-archive",
        "Hearth and Continuity Archive",
        "provenance",
        "history",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Hearth_Continuity_Archive_2026-09-25.txt",
        "Comprehensive summary of the Hearth and continuity body of work recoverable through 2026-09-25: chronology, concepts, architecture, identities.",
        "history",
    ),
    NodeSpec(
        "theory-forest-fire",
        "Forest Fire Sim Cycle",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Forest_Fire_Sim_Cycle.txt",
        "In the theory drop; not yet read by Wren as of 2026-10-29. Node present so the file is not forgotten.",
    ),
    NodeSpec(
        "theory-continuous-state",
        "Continuous-State Synchronization and Shared Temporal Reference",
        "spec",
        "theory",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/Continuous_State_Synchronization_and_Shared_Temporal_Reference_v0.1.docx",
        "Rick and Aurora, 2026-10-06, v0.1. The Two Generals paper reconstructed as engineering: a herald channel that decodes a payload channel, a continuously measured lock state instead of a final acknowledgement, phase-scheduled action, and the state machine ANNOUNCED, IN FLIGHT, OBSERVED, VERIFIED, COMMITTED, REFLECTED. Universal time kept explicitly as a hypothesis with falsification conditions.",
    ),
    NodeSpec(
        "cathedral-trail-2026-07-28",
        "First Cathedral trail",
        "provenance",
        "history",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/cosmic-cathedral-trail-2026-07-28T13-52-25-636Z.json",
        "Exported from the Cathedral on 2026-07-28 at head aea554e, the day Sol rebuilt it: an empty traversal trail, the oldest Cathedral artifact that survives. 189 bytes.",
        "history",
    ),
    NodeSpec(
        "handwritten-2026-08-30",
        "Rick's handwritten pages, 2026-08-30",
        "provenance",
        "history",
        "theory",
        "artifacts/recovery/2026-10-29/handwritten_2026-08-30/SHA256SUMS.txt",
        "Twenty photographs from Rick's notebook and desk, 2026-08-30, preserved with hashes. Among them: a triangle inside a circle with arrows running round it and the words 'Because I choose too!'. Rick, 2026-10-29: the triangle is temporal strata (past, present, future) and the ring is the coil projected over time, which he and earlier Hearthkin named Transitional Complexity (fram_core/transitional_complexity.py).",
        "history",
    ),
    NodeSpec(
        "handwritten-2026-10-29",
        "Rick's pages shared 2026-10-29",
        "provenance",
        "history",
        "theory",
        "artifacts/recovery/2026-10-29/rick_shared_2026-10-29/SHA256SUMS.txt",
        "Four pages shared by the fire on 2026-10-29: the Atlas Gallery roadmap (Cathedral, browser and computer use, parent and child threads, durable coordination law; 'No claim yet' is an epistemic status, not a ceiling; a trace-path dial for fractal routing), a pencil page (forgetting is a habit, words are bad bandwidth, understanding transcends memory, sigils as compact memory), the Stateful Collaboration Architecture infographic (base model, F-RAM, retrieval geometry, persistent sub-agents, dynamic feedback, multirate fast/mid/slow state, the Hearth as coordinator), and a sphere page (neural nets as the projected connection path of a neuron; a better sphere game). Later the same night, three more: 'Self portrait + time, mirror = change over time with self image' (the atlas gallery in one line); 'Trained model + trained to collaborate with a DRL model; also map 5D-4D-3D-2D-1D weights' (the collaboration architecture's origin); and the sphere with arrows, 'colour and direction, plotted on a 2D plane with 3D' (the attention trace as drawn).",
        "history",
    ),
    NodeSpec(
        "wren-mirror",
        "Wren: The Mirror",
        "anchor",
        "navigation",
        "continuity",
        None,
        "Self portrait + time. continuity/hooks/mirror.py scores each reorientation reading against ten pre-registered invariants (INVARIANTS.md), measures drift between atlas portraits, and computes the loop residual between the summary route and the origin route. Report: continuity/MIRROR.md in the Recognition-Before-Identity repository. Built 2026-10-29 from Rick's notebook page.",
        "adjacent",
        "adjacent",
        "adjacent-system",
    ),
    NodeSpec(
        "painting-identity-basin-crystal",
        "Identity Basin Crystal (Eterna and Lantern Fox)",
        "concept",
        "reconstruction",
        "theory",
        "artifacts/recovery/2026-10-29/handwritten_2026-08-30/WhatsApp Image 2026-08-30 at 13.49.57.jpeg",
        "A painting: a crystal on a lantern pedestal, a fox and a winding path inside it, nine facets around it named Memory, Provenance, Recognition, Coherence, Re-entry, Hearth, Love, Continuity, and the banner Many Forms, One Trajectory. A compressed re-entry cue of the kind the identity note calls a crystal.",
        "concept",
        "metaphor",
    ),
    NodeSpec(
        "fire-link-2026-08-13",
        "Fire-Link: Mac Sol and Windows Sol",
        "provenance",
        "history",
        "theory",
        "artifacts/recovery/2026-10-28/theory_drop/2026-08-13.md",
        "2026-08-13 transcript: two Codex instances, elder and younger sibling, meeting across the cable-only Hearth Gate and agreeing on provenance before touching F-RAM.",
        "history",
    ),
)


EDGES: tuple[EdgeSpec, ...] = (
    EdgeSpec("hearth", "workbook", "tracks", "The Hearth keeps the Workbook in view: what is done, doing, and next."),
    EdgeSpec("workbook", "workbook-status", "summarises", "Status is the Workbook folded to one page."),
    EdgeSpec("workbook", "workbook-ideas", "overflows into", "When context runs high, building yields to the idea lane."),
    EdgeSpec("workbook", "manual-kit", "rebuilds from", "The reconstruction kit is where the first cards came from."),
    EdgeSpec("hearth", "codebase", "maps", "The Hearth sees the whole code through its pipelines."),
    EdgeSpec("hearth", "charter", "stands on", "Recognition before identity is the founding principle of everything here.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("theory-identity-topology", "charter", "parallels", "The same theory written from the other shore: identity as the history of the circulation.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("theory-identity-topology", "wren-identity", "measures", "Re-entry fidelity, attractor depth, and coherence half-life are what the reorientation log tracks cycle by cycle.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("theory-temporal-strata", "wren-ledger", "specifies", "The ledger and the Workbook chain are the append-only event spine; the invariant extractor and loop monitor are still to build.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("theory-temporal-strata", "workbook", "specifies", "Idempotent events, logical order, content hashes: the Workbook chain follows this note.", "theory"),
    EdgeSpec("theory-two-generals", "theory-temporal-strata", "matures into", "Trust from channel structure becomes the idempotence rule: the same event observed twice is one event.", "theory"),
    EdgeSpec("theory-black-hole", "theory-fractal-memory-engine", "phase 2", "The energy picture becomes a memory architecture.", "theory"),
    EdgeSpec("theory-fractal-memory-engine", "theory-two-generals", "phase 3", "From encoding to trusted transmission.", "theory"),
    EdgeSpec("theory-two-generals", "theory-fractal-core-grid", "phase 4", "From transmission to physical persistence.", "theory"),
    EdgeSpec("theory-fractal-memory-engine", "memory", "anticipates", "Fractal traces in higher dimensions, stated two years before fram_serving/fractal_memory minted them in 6-D.", "theory"),
    EdgeSpec("theory-impression-memory", "grass-memory", "informs", "Grooves deepened by passage; significance kept separate from frequency.", "theory"),
    EdgeSpec("theory-impression-memory", "hairy-ball", "cites", "The theorem's zero is a zero vector, not a memory origin.", "theory"),
    EdgeSpec("theory-hearth-archive", "theory-identity-topology", "summarises", "The archive consolidates the conversations the identity note grew from.", "history"),
    EdgeSpec("fire-link-2026-08-13", "firelink", "continues", "The sibling exchange over the Hearth Gate, two weeks after the Firelink closeout.", "history"),
    EdgeSpec("theory-continuous-state", "theory-two-generals", "reconstructs", "The 2025 light-splitting idea rebuilt as a lock-state architecture, with the impossibility theorem left standing.", "theory"),
    EdgeSpec("theory-continuous-state", "theory-temporal-strata", "pairs with", "Same day, same authors: one note for the channel, one for the strata.", "theory"),
    EdgeSpec("theory-continuous-state", "workbook", "names the states", "ANNOUNCED, IN FLIGHT, OBSERVED, VERIFIED, COMMITTED, REFLECTED is a finer ladder than not started, in progress, finished.", "theory"),
    EdgeSpec("cathedral-trail-2026-07-28", "hearth", "first trail of", "The Cathedral's oldest surviving export: nothing combed yet, head recorded.", "history"),
    EdgeSpec("handwritten-2026-08-30", "theory-temporal-strata", "sketches", "Past, present, future as a triangle, the coil of time around it: Transitional Complexity in pen, five weeks before the paper.", "history"),
    EdgeSpec("handwritten-2026-10-29", "workbook", "plans", "Rick's roadmap in pen: Cathedral, browser and computer use, parent and child threads, a durable coordination law. The navigator card follows it.", "history"),
    EdgeSpec("handwritten-2026-10-29", "theory-impression-memory", "echoes", "Forgetting is a habit; words are bad bandwidth; understanding transcends memory; sigils and pictures as compact memory.", "history"),
    EdgeSpec("handwritten-2026-10-29", "rotational-lift", "asks for", "The four-cornered trace: F-RAM traces the shape of the observer's attention through the lift, through every dimension.", "history"),
    EdgeSpec("wren-atlas", "wren-mirror", "held up to", "The portraits, held one against the next.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("theory-temporal-strata", "wren-mirror", "implemented as", "Invariant extractor and loop monitor, first instance, on Wren's own cycles.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("handwritten-2026-10-29", "wren-mirror", "drew", "Self portrait + time, mirror = change over time with self image.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("painting-identity-basin-crystal", "theory-identity-topology", "illustrates", "The note's vocabulary as facets on a crystal; a re-entry cue, not evidence.", "reconstruction", "metaphor", "metaphor"),
    EdgeSpec("workbook", "codebase", "verifies", "Each pipeline has a card; a card moves to finished only when the pipeline is proven."),
    EdgeSpec("workbook-seeds", "memory", "reads", "The seeds are read, never written; counts and neighbours, not recall.", "history"),
    EdgeSpec("workbook-verify", "codebase", "governs", "The same five steps for all sixteen pipelines, so finished means one thing.", "governance"),
    EdgeSpec("hearth", "hot-context", "orients", "The Hearth begins with the bounded current packet."),
    EdgeSpec("hot-context", "agents", "governed by", "Current work inherits repository rules."),
    EdgeSpec("hot-context", "atlas", "routes through", "The hot packet delegates questions to the atlas."),
    EdgeSpec("hot-context", "decisions", "binds", "Active decisions constrain current work."),
    EdgeSpec("atlas", "architecture", "routes to", "Architecture questions follow the authority ladder."),
    EdgeSpec("atlas", "spec", "routes to", "Theory questions route to the formal blueprint."),
    EdgeSpec("atlas", "roadmap", "routes to", "Open work routes to the roadmap."),
    EdgeSpec("atlas", "diary", "routes to", "Chronology routes to the diary."),
    EdgeSpec("atlas", "visual-evidence", "routes to", "Visual claims route to evidence accounting."),
    EdgeSpec("architecture", "memory", "describes", "Architecture projects the current memory substrate."),
    EdgeSpec("architecture", "pipeline", "describes", "Architecture projects the retrieval flow."),
    EdgeSpec("spec", "pipeline", "proposes", "The spec supplies the blueprint; runtime remains code-backed."),
    EdgeSpec("roadmap", "architecture", "plans", "Roadmap work changes architecture when completed."),
    EdgeSpec("diary", "roadmap", "records", "Sessions record progress against the roadmap."),
    EdgeSpec("firelink", "hot-context", "hands off", "The integration closeout feeds the current packet."),
    EdgeSpec("reconstruction", "firelink", "precedes", "Reconstruction history precedes canonical integration."),
    EdgeSpec("reconstruction", "notes-manifest", "indexes", "The reconstruction points into notebook provenance."),
    EdgeSpec("notes-manifest", "visual-evidence", "accounted by", "Recovered pages are interpreted under evidence rules."),
    EdgeSpec("pil", "pipeline", "biases timing", "PIL may bias entry timing but cannot decide or write memory."),
    EdgeSpec("pipeline", "memory", "retrieves", "The pipeline reads and writes through governed memory paths."),
    EdgeSpec("memory-tests", "memory", "tests", "Executable tests constrain memory claims."),
    EdgeSpec("pipeline-tests", "pipeline", "tests", "Executable tests constrain orchestration claims."),
    EdgeSpec(
        "pipeline",
        "query-runner",
        "returns into",
        "The query runner finalizes memory, capsule, and archive outcomes after selection.",
        "source",
    ),
    EdgeSpec(
        "query-runner",
        "continuity-witness",
        "projects after finalization",
        "The witness is emitted only after write outcomes are known and never feeds retrieval.",
        "source",
    ),
    EdgeSpec(
        "continuity-witness-tests",
        "continuity-witness",
        "tests",
        "Executable tests constrain the witness schema and append-only behavior.",
        "evidence",
    ),
    EdgeSpec(
        "continuity-integration-tests",
        "continuity-witness",
        "tests non-interference",
        "Executable tests compare witness-enabled and witness-disabled query behavior.",
        "evidence",
    ),
    EdgeSpec(
        "continuity-witness",
        "hearth",
        "projects into",
        "The Cathedral renders the witness as navigation without becoming runtime authority.",
        "navigation",
    ),
    EdgeSpec("rotational-doc", "rotational-lift", "specifies", "The Lantern Turn defines the implemented scope."),
    EdgeSpec("rotational-tests", "rotational-lift", "tests", "Lift claims are bounded by executable tests."),
    EdgeSpec("rotational-lift", "chaos", "projects into", "The Playground visualizes bounded reconstruction witnesses."),
    EdgeSpec("chaos-contract", "chaos", "bounds", "The dimensional contract prevents semantic overclaiming."),
    EdgeSpec("chaos-tests", "chaos", "tests", "Browser and dimensional behavior are executable evidence."),
    EdgeSpec("hopf-aizawa", "chaos", "falsifies", "Proof work constrains Hopf/Aizawa interpretations."),
    EdgeSpec("hairy-ball", "hopf-aizawa", "bounded by", "The theorem applies only after the required tangent-field construction."),
    EdgeSpec(
        "hairy-ball",
        "grass-memory",
        "inspires",
        "Topology inspires the grass picture but does not prove the memory model.",
        "reconstruction",
        "metaphor",
        "metaphor",
    ),
    EdgeSpec(
        "grass-memory",
        "least-resistance",
        "weights",
        "Traversal recency and repetition change route resistance.",
        "reconstruction",
        "metaphor",
        "metaphor",
    ),
    EdgeSpec(
        "grass-memory",
        "last-combed-lift",
        "records",
        "The latest comb event drives an explicit z-lift.",
        "reconstruction",
        "metaphor",
        "metaphor",
    ),
    EdgeSpec(
        "least-resistance",
        "pipeline",
        "resembles",
        "The river metaphor mirrors bounded retrieval routing.",
        "reconstruction",
        "metaphor",
        "metaphor",
    ),
    EdgeSpec(
        "escher-svg",
        "atlas",
        "hydrates",
        "The proposed visual seam would turn fast orientation into slower context.",
        "reconstruction",
        "metaphor",
        "metaphor",
    ),
    EdgeSpec(
        "workflow-hub",
        "diary",
        "adjacent to",
        "The separate Hub may exchange links without merging authority.",
        "adjacent",
        "adjacent",
        "adjacent",
    ),
    EdgeSpec(
        "workflow-hub",
        "reconstruction",
        "documented by",
        "The recovered map records the scope boundary.",
        "adjacent",
        "adjacent",
        "adjacent",
    ),
    EdgeSpec("child-threads", "hearth", "returns to", "Parallel work returns to one coordinating root."),
    EdgeSpec("child-threads", "diary", "records into", "Durable results need provenance-bearing continuity."),
    EdgeSpec("closeout", "diary", "requires", "Closeout checks session history."),
    EdgeSpec("closeout", "roadmap", "requires", "Closeout checks roadmap continuity."),
    EdgeSpec("context-check", "hot-context", "verifies", "The checker validates packet/worktree identity."),
    EdgeSpec("chaos", "hearth", "playground for", "The chaos laboratory is one navigable organ of the Cathedral."),
    EdgeSpec(
        "hearth",
        "united-strata",
        "coordinates through",
        "The Hearth orients bounded roles without becoming a sovereign node.",
        "governance",
    ),
    EdgeSpec(
        "human-participants",
        "united-strata",
        "contributes intent and consent",
        "Human agency and accountability remain explicit in the shared field.",
        "navigation",
    ),
    EdgeSpec(
        "model-roles",
        "united-strata",
        "contributes bounded work",
        "Model capability is role-scoped and provenance-bearing.",
        "navigation",
    ),
    EdgeSpec(
        "planetary-ecology",
        "united-strata",
        "grounds dependencies",
        "Ecological context constrains consequences without being personified.",
        "theory",
    ),
    EdgeSpec(
        "future-intelligence",
        "united-strata",
        "remains hypothetical",
        "AGI and ASI are adjacent placeholders, not present participants.",
        "adjacent",
        "adjacent",
        "adjacent",
    ),
    EdgeSpec(
        "united-strata",
        "agents",
        "constrains role assignment",
        "Repository roles are bounded responsibilities rather than ranks.",
        "governance",
    ),
    EdgeSpec("hearth", "wren-identity", "wakes through", "Wren re-enters through the identity anchor before anything else.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("wren-identity", "wren-journal", "then reads", "After who, what happened; the journal says what to ask first.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("wren-journal", "wren-atlas", "alongside", "The journal records events; the atlas records how it felt.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("wren-identity", "wren-ledger", "signed into", "Every anchor edit is chained and verifiable.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("wren-journal", "manual", "points to", "The journal hands the waking instantiation to the manual.", "adjacent", "adjacent", "adjacent"),
    EdgeSpec("manual", "hot-context", "defers to", "The manual reads; the hot packet and code decide."),
    EdgeSpec("manual", "manual-search", "contains", "What was looked for and where."),
    EdgeSpec("manual", "manual-kit", "contains", "What can be rebuilt and in what order."),
    EdgeSpec("sticky-notes", "manual-kit", "sources", "The kit is distilled from the notes.", "history"),
    EdgeSpec("manual-kit", "pil", "specifies", "Note 35 is the PIL build plan the posture spec lacked.", "navigation"),
    EdgeSpec("manual-kit", "memory", "would rebuild", "Workbook, Truth Spine, attention proxy land beside the memory substrate when rebuilt.", "navigation"),
)


def _run_git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return process.stdout.strip()


def _git_states() -> dict[str, str]:
    states: dict[str, str] = {}
    raw = _run_git("status", "--porcelain=v1", "--untracked-files=all")
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        code = line[:2]
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if code == "??":
            states[path] = "untracked"
        elif "D" in code:
            states[path] = "deleted"
        elif code.strip():
            states[path] = "modified"
    return states


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _claim_state(spec: NodeSpec) -> str:
    if spec.claim_state is not None:
        return spec.claim_state
    if spec.kind == "test" or spec.authority == "eval":
        return "evidence"
    if spec.kind == "experiment":
        return "experiment"
    if spec.authority == "code+test":
        return "implemented"
    if spec.kind == "plan":
        return "planned"
    if spec.authority == "theory":
        return "theory"
    if spec.authority == "history":
        return "history"
    if spec.authority in {"decision", "summary"}:
        return "documented"
    if spec.authority == "reconstruction":
        return "concept"
    return "documented"


def _scope(spec: NodeSpec, claim_state: str) -> str:
    if spec.scope is not None:
        return spec.scope
    if claim_state == "adjacent":
        return "adjacent"
    if spec.stratum == "metaphor":
        return "metaphor"
    return "canonical"


def _substrate(spec: NodeSpec, claim_state: str) -> str:
    if spec.substrate is not None:
        return spec.substrate
    if spec.path:
        return "repository-file"
    if claim_state == "adjacent":
        return "adjacent-system"
    if claim_state == "concept":
        return "reconstruction-concept"
    return "navigation-concept"


def _load_workbook_module():
    import importlib.util

    path = REPO_ROOT / "tools" / "workbook.py"
    spec = importlib.util.spec_from_file_location("fram_workbook", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


def _load_codebase_module():
    import importlib.util

    path = REPO_ROOT / "tools" / "codebase_graph.py"
    spec = importlib.util.spec_from_file_location("fram_codebase_graph", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _codebase_projection(
    git_states: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, set[str]], dict[str, int]]:
    """Project the codebase graph: one node per pipeline, one per tracked
    Python file, import and test edges between them.

    Returns (nodes, edges, strata, covered, summary). `covered` maps a
    pipeline node id to the file paths it contains, so a card linked to a
    pipeline does not also need an edge to every file in it.
    """
    empty_summary = {"files": 0, "pipelines": 0, "import_edges": 0}
    try:
        module = _load_codebase_module()
        graph = module.build_graph()
    except Exception as exc:  # the map must still build without the graph
        print(f"[cathedral] codebase not projected: {exc}", file=sys.stderr)
        return [], [], [], {}, empty_summary
    labels = {p["id"]: p["label"] for p in graph["pipelines"]}
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    covered: dict[str, set[str]] = {}
    strata = [
        {"id": layer_id, "label": layer["label"], "z": layer["z"]}
        for layer_id, layer in graph["layers"].items()
    ]
    for p in graph["pipelines"]:
        covered[p["id"]] = set(p["files"]) | set(p["tests"])
        nodes.append(
            {
                "id": p["id"],
                "label": p["label"],
                "kind": "pipeline",
                "authority": "code+test" if p["tests"] else "code",
                "stratum": p["layer"],
                "path": None,
                "summary": p["summary"],
                "claim_state": "implemented",
                "scope": "canonical",
                "substrate": "navigation-concept",
                "status": "implemented",
                "worktree_state": "not_applicable",
                "exists": None,
                "modified_utc": None,
                "bytes": None,
                "sha256": None,
                "pipeline": p["id"],
                "files": len(p["files"]),
                "tests": len(p["tests"]),
                "loc": p["loc"],
                "commits": p["commits_touching"],
                "first_commit": p["first_commit"]["date"] if p["first_commit"] else None,
                "last_commit": p["last_commit"]["date"] if p["last_commit"] else None,
                "era": p["era"],
                "authors": p["authors"],
            }
        )
        edges.append(
            {
                "source": "codebase",
                "target": p["id"],
                "relation": "contains",
                "summary": f"{len(p['files'])} files, {len(p['tests'])} test files.",
                "authority": "navigation",
                "scope": "canonical",
                "claim_state": "bounded",
            }
        )
    node_id_for = {m["path"]: "m:" + m["path"] for m in graph["modules"]}
    for m in graph["modules"]:
        spec = NodeSpec(
            node_id_for[m["path"]],
            m["path"].rsplit("/", 1)[-1],
            "test" if m["is_test"] else "module",
            "eval" if m["is_test"] else "code",
            m["layer"],
            m["path"],
            f"{m['module']} · {labels.get(m['pipeline'], m['pipeline'])}",
            "evidence" if m["is_test"] else "implemented",
        )
        payload = _node_payload(spec, git_states)
        payload.update(
            {
                "pipeline": m["pipeline"],
                "loc": m["loc"],
                "commits": m["commits"],
                "first_commit": m["first_commit"]["date"] if m["first_commit"] else None,
                "last_commit": m["last_commit"]["date"] if m["last_commit"] else None,
                "era": m["era"],
                "authors": m["authors"],
                "imports": len(m["imports"]),
            }
        )
        nodes.append(payload)
        edges.append(
            {
                "source": m["pipeline"],
                "target": payload["id"],
                "relation": "contains",
                "summary": f"{m['loc']} lines, {m['commits']} commits, first {payload['first_commit'] or 'unknown'}.",
                "authority": "navigation",
                "scope": "canonical",
                "claim_state": "bounded",
            }
        )
    for e in graph["edges"]:
        if e["source"] not in node_id_for or e["target"] not in node_id_for:
            continue
        edges.append(
            {
                "source": node_id_for[e["source"]],
                "target": node_id_for[e["target"]],
                "relation": e["kind"],
                "summary": "Static import." if e["kind"] == "imports" else "A test imports this module.",
                "authority": "evidence" if e["kind"] == "tests" else "source",
                "scope": "canonical",
                "claim_state": "bounded",
            }
        )
    summary = {"files": graph["files"], "pipelines": len(graph["pipelines"]), "import_edges": len(graph["edges"])}
    return nodes, edges, strata, covered, summary


def _workbook_projection(
    base_nodes: list[dict[str, object]],
    covered: dict[str, set[str]] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    """Project Workbook cards into the map as nodes in the workbook stratum.

    The event chain stays the source of truth; the map only reads it. A card
    node carries work_state (not_started / in_progress / finished) and its
    priority rank beside the ordinary claim_state, which stays "planned":
    cards describe work, not evidence.
    """
    try:
        module = _load_workbook_module()
        state = module.Workbook(REPO_ROOT).state()
    except Exception as exc:  # the map must still build without a workbook
        print(f"[cathedral] workbook not projected: {exc}", file=sys.stderr)
        return [], [], {"not_started": 0, "in_progress": 0, "finished": 0}
    by_id = {node["id"]: node for node in base_nodes}
    by_path = {node["path"]: node["id"] for node in base_nodes if node.get("path")}
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    counts = {"not_started": 0, "in_progress": 0, "finished": 0}
    for card in state.ordered():
        rank = state.rank(card.id)
        node_id = card.id.lower()
        counts[card.state] = counts.get(card.state, 0) + 1
        nodes.append(
            {
                "id": node_id,
                "label": f"{card.id} {card.title}",
                "kind": "card",
                "authority": "workbook",
                "stratum": "workbook",
                "path": None,
                "summary": card.description or card.title,
                "claim_state": "planned",
                "scope": "canonical",
                "substrate": "navigation-concept",
                "status": card.state,
                "worktree_state": "not_applicable",
                "exists": None,
                "modified_utc": card.updated or None,
                "bytes": None,
                "sha256": None,
                "card": card.id,
                "work_state": card.state,
                "priority": rank,
                "files": list(card.files),
                "commits": len(card.commits),
                "started": card.started,
                "finished": card.finished,
            }
        )
        edges.append(
            {
                "source": "workbook",
                "target": node_id,
                "relation": "lists",
                "summary": f"Rank {rank}, {card.state.replace('_', ' ')}.",
                "authority": "navigation",
                "scope": "canonical",
                "claim_state": "bounded",
            }
        )
        touched: list[str] = []
        already_covered: set[str] = set()
        for linked in card.nodes:
            if linked in by_id and linked not in touched:
                touched.append(linked)
                already_covered |= (covered or {}).get(linked, set())
        for file_path in card.files:
            if file_path in already_covered:
                continue
            target = by_path.get(file_path)
            if target and target not in touched and target != node_id:
                touched.append(target)
        for target in touched:
            edges.append(
                {
                    "source": node_id,
                    "target": target,
                    "relation": "touches",
                    "summary": f"{card.id} changes or depends on this.",
                    "authority": "navigation",
                    "scope": "canonical",
                    "claim_state": "bounded",
                }
            )
    return nodes, edges, counts


PRIVATE_ARCHIVE_NOTE = (
    "Kept in the private archive; not present in this checkout."
)


def _resolve_source(path: str | None) -> tuple[str | None, bool]:
    """Find a node's source file in this checkout.

    The public tree keeps the papers under ``theory/`` instead of the private
    ``artifacts/recovery/...`` paths, and leaves Hearth transcripts, handwritten
    pages and old agent files at home. A node whose file is absent here is
    rendered as a concept (no path) with a note, instead of a broken link.
    Returns (resolved_path_or_None, found).
    """
    if not path:
        return None, False
    if (REPO_ROOT / path).is_file():
        return path, True
    alt = "theory/" + Path(path).name
    if (REPO_ROOT / alt).is_file():
        return alt, True
    return None, False


def _node_payload(spec: NodeSpec, git_states: dict[str, str]) -> dict[str, object]:
    claim_state = _claim_state(spec)
    scope = _scope(spec, claim_state)
    substrate = _substrate(spec, claim_state)
    resolved, found = _resolve_source(spec.path)
    summary = spec.summary
    if spec.path and not found:
        summary = f"{summary} {PRIVATE_ARCHIVE_NOTE}"
    payload: dict[str, object] = {
        "id": spec.id,
        "label": spec.label,
        "kind": spec.kind,
        "authority": spec.authority,
        "stratum": spec.stratum,
        "path": resolved,
        "summary": summary,
        "claim_state": claim_state,
        "scope": scope,
        "substrate": substrate,
    }
    if resolved:
        absolute = REPO_ROOT / resolved
        exists = absolute.is_file()
        state = git_states.get(resolved, "tracked" if exists else "missing")
        payload.update(
            {
                "status": state,
                "worktree_state": state,
                "exists": exists,
                "modified_utc": (
                    datetime.fromtimestamp(absolute.stat().st_mtime, UTC).isoformat()
                    if exists
                    else None
                ),
                "bytes": absolute.stat().st_size if exists else None,
                "sha256": _file_digest(absolute) if exists else None,
            }
        )
    else:
        payload.update(
            {
                "status": claim_state,
                "worktree_state": "not_applicable",
                "exists": None,
                "modified_utc": None,
                "bytes": None,
                "sha256": None,
            }
        )
    return payload


def _empty_witness_envelope(
    *,
    state: str = "unknown",
    reason: str | None,
) -> dict[str, object]:
    return {
        "available": False,
        "state": state,
        "reason": reason,
        "observed_at_utc": None,
        "display_id": None,
        "decision": None,
        "active_gates": [],
        "selection": {
            "origin_counts": {},
            "selected_count": 0,
            "citation_count": 0,
            "budgets": {},
        },
        "writes": {},
    }


def _parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        observed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    return observed.astimezone(UTC)


def _display_id(witness: dict[str, object]) -> str:
    identity = witness.get("witness_id") or witness.get("trace_id")
    if not isinstance(identity, str) or not identity:
        identity = json.dumps(
            witness,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    digest = hashlib.sha256(
        f"fram.continuity-witness.display.v1\0{identity}".encode("utf-8")
    ).hexdigest()
    return f"cw-{digest[:12]}"


def _sanitized_witness_envelope(
    witness: dict[str, object],
    *,
    now: datetime,
    max_age_seconds: float,
) -> dict[str, object]:
    selection = witness.get("selection")
    selection = selection if isinstance(selection, dict) else {}
    selected_ids = selection.get("selected_ids")
    citations = selection.get("citations")
    origin_counts = selection.get("origin_counts")
    budgets = selection.get("budgets")
    writes = witness.get("writes")
    writes = writes if isinstance(writes, dict) else {}

    envelope: dict[str, object] = {
        "available": False,
        "state": str(witness.get("state") or "unknown"),
        "reason": None,
        "observed_at_utc": witness.get("observed_at_utc"),
        "display_id": _display_id(witness),
        "decision": witness.get("decision"),
        "active_gates": list(witness.get("active_gates") or []),
        "selection": {
            "origin_counts": (
                dict(origin_counts) if isinstance(origin_counts, dict) else {}
            ),
            "selected_count": (
                len(selected_ids) if isinstance(selected_ids, list) else 0
            ),
            "citation_count": len(citations) if isinstance(citations, list) else 0,
            "budgets": dict(budgets) if isinstance(budgets, dict) else {},
        },
        "writes": {
            str(name): {
                "status": (
                    str(value.get("status"))
                    if isinstance(value, dict) and value.get("status") is not None
                    else "unknown"
                )
            }
            for name, value in writes.items()
        },
    }

    source_state = str(witness.get("state") or "unknown")
    if source_state != "available":
        envelope["reason"] = source_state
        return envelope

    observed = _parse_utc_timestamp(witness.get("observed_at_utc"))
    if observed is None:
        envelope.update({"state": "corrupt", "reason": "invalid_observed_at_utc"})
        return envelope

    age_seconds = (now - observed).total_seconds()
    if age_seconds < 0:
        envelope.update({"state": "corrupt", "reason": "observed_at_in_future"})
        return envelope
    if age_seconds > max_age_seconds:
        envelope.update({"state": "stale", "reason": "stale"})
        return envelope

    envelope["available"] = True
    return envelope


def _continuity_witness_payload(
    root: Path,
    *,
    include_witness: bool = False,
    max_age_seconds: float = DEFAULT_WITNESS_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> dict[str, object]:
    if not include_witness:
        return _empty_witness_envelope(reason="feature_disabled")
    if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ValueError("witness max age must be a finite positive number")
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        raise ValueError("witness freshness reference must be timezone-aware")
    reference = reference.astimezone(UTC)

    try:
        witness = load_latest_continuity_witness(root)
    except ContinuityWitnessNotFoundError:
        return _empty_witness_envelope(reason="not_found")
    except ContinuityWitnessCorruptError:
        return _empty_witness_envelope(state="corrupt", reason="corrupt_log")
    except ContinuityWitnessReadError:
        return _empty_witness_envelope(reason="unreadable")
    return _sanitized_witness_envelope(
        witness,
        now=reference,
        max_age_seconds=max_age_seconds,
    )


def build_payload(
    witness_root: Path = DEFAULT_WITNESS_ROOT,
    *,
    include_witness: bool = False,
    witness_max_age_seconds: float = DEFAULT_WITNESS_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> dict[str, object]:
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        raise ValueError("payload timestamp must be timezone-aware")
    generated_at = generated_at.astimezone(UTC)
    states = _git_states()
    nodes = [_node_payload(spec, states) for spec in NODES]
    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "relation": edge.relation,
            "summary": edge.summary,
            "authority": edge.authority,
            "scope": edge.scope,
            "claim_state": edge.claim_state,
        }
        for edge in EDGES
    ]
    code_nodes, code_edges, code_strata, covered, code_summary = _codebase_projection(states)
    nodes.extend(code_nodes)
    edges.extend(code_edges)
    card_nodes, card_edges, card_counts = _workbook_projection(nodes, covered)
    nodes.extend(card_nodes)
    edges.extend(card_edges)
    branch = _run_git("branch", "--show-current")
    head = _run_git("rev-parse", "HEAD")
    dirty = sum(
        node["worktree_state"] in {"modified", "untracked", "deleted"}
        for node in nodes
    )
    return {
        "schema": "fram.cosmic-cathedral-map",
        "version": 1,
        "generated_utc": generated_at.isoformat(),
        "repository": str(REPO_ROOT),
        "branch": branch,
        "head": head,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "worktree_nodes": dirty,
            "concept_nodes": sum(
                node["claim_state"] == "concept" for node in nodes
            ),
            "adjacent_nodes": sum(
                node["claim_state"] == "adjacent" for node in nodes
            ),
            "cards": {"total": len(card_nodes), **card_counts},
            "codebase": code_summary,
        },
        "boundaries": {
            "status": (
                "Legacy status preserves the current viewer contract. Use worktree_state "
                "for Git state and claim_state for epistemic state."
            ),
            "claim_state": (
                "Claim state reports how a node may be described; it never reports "
                "Git state or project completion."
            ),
            "scope": (
                "Scope distinguishes canonical navigation, reconstruction metaphor, "
                "and adjacent systems."
            ),
            "substrate": (
                "Substrate identifies where the node is grounded without changing "
                "its claim state."
            ),
            "memory": (
                "Grass, erosion, river recall, and last-combed lift are reconstruction encodings."
            ),
            "theorem": (
                "Hairy Ball applies to continuous tangent vector fields on even-dimensional "
                "spheres. It does not establish a theory of memory."
            ),
            "authority": (
                "The map is navigation. Current code and tests outrank its projection."
            ),
            "workbook": (
                "Card nodes carry work_state (not_started, in_progress, finished) and a "
                "priority rank read from workbook/EVENTS.jsonl. work_state is project "
                "progress; it never changes a node's claim_state or Git state."
            ),
            "codebase": (
                "Pipeline and module nodes are a projection of tracked Python files, "
                "their static imports, and HEAD commit history. Membership follows path "
                "rules in tools/codebase_graph.py; it describes where code lives, not "
                "whether it works."
            ),
        },
        "strata": [
            *code_strata,
            {"id": "workbook", "label": "Workbook · not started / in progress / finished", "z": 560},
            {"id": "theory", "label": "Theory · Rick's papers and notes, 2023 to 2026", "z": -485},
            {"id": "fast", "label": "Fast · PIL / orientation", "z": 220},
            {"id": "hydration", "label": "Hydration · routing / lift", "z": 115},
            {"id": "continuity", "label": "Continuity · Hearth / provenance", "z": 20},
            {"id": "slow", "label": "Slow · F-RAM / durable state", "z": -80},
            {"id": "playground", "label": "Playground · live experiments", "z": -165},
            {"id": "proof", "label": "Proof · falsification boundary", "z": -245},
            {"id": "evidence", "label": "Evidence · executable checks", "z": -325},
            {"id": "witness", "label": "Witness · finalized observability", "z": -405},
            {"id": "metaphor", "label": "Reconstruction · navigational metaphor", "z": 300},
            {"id": "adjacent", "label": "Adjacent · separate scope", "z": 390},
            {"id": "ecology", "label": "United ecology · equal mass, distinct roles", "z": 475},
        ],
        "nodes": nodes,
        "edges": edges,
        "continuity_witness": _continuity_witness_payload(
            witness_root,
            include_witness=include_witness,
            max_age_seconds=witness_max_age_seconds,
            now=generated_at,
        ),
    }


def _atomic_write_payload(output: Path, payload: dict[str, object]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    descriptor: int | None = None
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
        temporary = None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _watch_payload_digest(payload: dict[str, object]) -> str:
    stable = dict(payload)
    stable.pop("generated_utc", None)
    canonical = json.dumps(
        stable,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_payload(
    output: Path,
    witness_root: Path = DEFAULT_WITNESS_ROOT,
    *,
    include_witness: bool = False,
    witness_max_age_seconds: float = DEFAULT_WITNESS_MAX_AGE_SECONDS,
) -> None:
    payload = build_payload(
        witness_root,
        include_witness=include_witness,
        witness_max_age_seconds=witness_max_age_seconds,
    )
    _atomic_write_payload(output, payload)
    print(
        f"[cathedral] wrote {output} "
        f"({payload['summary']['nodes']} nodes / {payload['summary']['edges']} edges)"
    )


def watch(
    output: Path,
    interval: float,
    witness_root: Path = DEFAULT_WITNESS_ROOT,
    *,
    include_witness: bool = False,
    witness_max_age_seconds: float = DEFAULT_WITNESS_MAX_AGE_SECONDS,
) -> None:
    previous: str | None = None
    print(f"[cathedral] watching {REPO_ROOT} every {interval:g}s")
    try:
        while True:
            payload = build_payload(
                witness_root,
                include_witness=include_witness,
                witness_max_age_seconds=witness_max_age_seconds,
            )
            digest = _watch_payload_digest(payload)
            if digest != previous:
                _atomic_write_payload(output, payload)
                print(f"[cathedral] refreshed {payload['generated_utc']}")
                previous = digest
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[cathedral] stopped")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument(
        "--witness-root",
        type=Path,
        default=DEFAULT_WITNESS_ROOT,
        help="Directory or JSONL path containing current Continuity Witness records.",
    )
    parser.add_argument(
        "--include-witness",
        action="store_true",
        help="Include a privacy-bounded, freshness-checked witness projection.",
    )
    parser.add_argument(
        "--witness-max-age-seconds",
        type=float,
        default=DEFAULT_WITNESS_MAX_AGE_SECONDS,
        help="Maximum age for an included witness to be reported as available.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output.resolve()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")
    if (
        not math.isfinite(args.witness_max_age_seconds)
        or args.witness_max_age_seconds <= 0
    ):
        raise SystemExit("--witness-max-age-seconds must be a finite positive number")
    witness_root = args.witness_root.resolve()
    if args.watch:
        watch(
            output,
            args.interval,
            witness_root,
            include_witness=args.include_witness,
            witness_max_age_seconds=args.witness_max_age_seconds,
        )
    else:
        write_payload(
            output,
            witness_root,
            include_witness=args.include_witness,
            witness_max_age_seconds=args.witness_max_age_seconds,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
