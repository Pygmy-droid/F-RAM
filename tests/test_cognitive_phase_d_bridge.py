from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fram_core.pipeline import QueryOrchestrator
from fram_serving.config import FRAMConfig
from fram_serving import app as app_mod
from fram_serving.app import _apply_phase_d_memory_bridge
from fram_serving.scoring._fractal_trace_scores_phase_d import phase_d_score_batch


DATA_ROOT = Path(__file__).resolve().parents[1] / "examples" / "data"


def test_cognitive_phase_d_bridge_harness():
    """Minimal harness to exercise cognitive->Phase D bridge without changing serving."""
    engine = QueryOrchestrator(config=FRAMConfig(), tracer=None, data_root=DATA_ROOT)

    shortlist = [
        {"text": "cognitive memory alpha signal"},
        {"text": "cognitive memory beta signal"},
    ]
    query_vec, episode_vecs = engine.get_embeddings_for_shortlist("memory bridge query", shortlist)

    assert query_vec and episode_vecs
    assert len(episode_vecs) == len(shortlist)

    result = phase_d_score_batch(
        query_embedding=query_vec,
        episode_embeddings=episode_vecs,
        phase_d_enabled=True,
        phase_d_debug=True,
    )

    assert result["scores"] and len(result["scores"]) == len(shortlist)
    diag = result["diagnostics"].get("phase_d")
    assert diag is not None
    assert 0.0 <= diag["alpha_t"] <= 1.0


def test_phase_d_memory_bridge_gated(monkeypatch):
    original = app_mod.CFG.phase_d.model_copy()
    try:
        candidates = [
            {"text": "first memory chunk"},
            {"text": "second memory chunk"},
        ]

        class _StubOrchestrator:
            def get_embeddings_for_shortlist(self, query_text, shortlist):
                dim = 4
                q = [0.1] * dim
                eps = [[0.2] * dim for _ in shortlist]
                return q, eps

        monkeypatch.setattr(app_mod, "_get_orchestrator", lambda: _StubOrchestrator())

        app_mod.CFG.phase_d.enabled = True
        app_mod.CFG.phase_d.enable_memory_bridge = False
        out, diag = _apply_phase_d_memory_bridge("q", list(candidates), debug=True)
        assert all("phase_d_score" not in c for c in out)
        assert diag is None

        app_mod.CFG.phase_d.enable_memory_bridge = True
        out_on, diag_on = _apply_phase_d_memory_bridge("q", list(candidates), debug=True)
        assert all("phase_d_score" in c for c in out_on)
        assert diag_on is not None
        assert 0.0 <= diag_on["alpha_t"] <= 1.0
    finally:
        app_mod.CFG.phase_d.enabled = original.enabled
        app_mod.CFG.phase_d.enable_memory_bridge = original.enable_memory_bridge
        app_mod.CFG.phase_d.debug_observability = original.debug_observability


def test_phase_d_memory_bridge_perf(monkeypatch):
    original = app_mod.CFG.phase_d.model_copy()
    try:
        class _StubOrchestrator:
            def get_embeddings_for_shortlist(self, query_text, shortlist):
                dim = 32
                q = [0.1] * dim
                eps = [[(i % 5) * 0.1 for _ in range(dim)] for i in range(len(shortlist))]
                return q, eps

        candidates = [{"text": f"memory chunk {i}"} for i in range(64)]
        app_mod.CFG.phase_d.enabled = True
        app_mod.CFG.phase_d.enable_memory_bridge = True
        monkeypatch.setattr(app_mod, "_get_orchestrator", lambda: _StubOrchestrator())
        start = perf_counter()
        out, diag = _apply_phase_d_memory_bridge("query", candidates, debug=False)
        elapsed = perf_counter() - start
        assert out and len(out) == len(candidates)
        assert elapsed < 0.3
        assert diag is None
    finally:
        app_mod.CFG.phase_d.enabled = original.enabled
        app_mod.CFG.phase_d.enable_memory_bridge = original.enable_memory_bridge
        app_mod.CFG.phase_d.debug_observability = original.debug_observability
