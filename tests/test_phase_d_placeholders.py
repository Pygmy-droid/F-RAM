"""Smoke test for Phase D scaffolding.

Verifies that the implemented modules import cleanly and serve the smoke contract.
"""

from fastapi.testclient import TestClient

from fram_serving.app import app as fastapi_app


def test_import_phase_d_modules():
    import fram_serving.embedding.quaternion_adapter as qa
    import fram_serving.scoring._fractal_trace_scores_phase_d as fsd

    assert callable(qa.build_projection_matrix)
    assert callable(fsd.compute_logistic_alpha)


def test_phase_d_score_batch_smoke():
    from fram_serving.scoring._fractal_trace_scores_phase_d import phase_d_score_batch

    query = [1.0, 0.0, 0.0, 0.0]
    episodes = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
    ]
    result = phase_d_score_batch(
        query, episodes, phase_d_enabled=False, phase_d_debug=False
    )
    assert "scores" in result and "diagnostics" in result
    assert len(result["scores"]) == len(episodes)
    assert result["diagnostics"]["phase_d"] is None

    debug_result = phase_d_score_batch(
        query, episodes, phase_d_enabled=True, phase_d_debug=True
    )
    assert debug_result["diagnostics"]["phase_d"] is not None


def test_phase_d_logistic_blend_tuning():
    from fram_serving.scoring._fractal_trace_scores_phase_d import (
        combine_quaternion_similarity,
        compute_logistic_alpha_from_delta,
    )

    alpha_low = compute_logistic_alpha_from_delta(vec_sim=0.8, quat_sim=0.2)
    alpha_high = compute_logistic_alpha_from_delta(vec_sim=0.2, quat_sim=0.8)
    assert alpha_high > 0.5
    assert alpha_low < 0.5
    # Tuned gain should separate the regimes
    assert (alpha_high - alpha_low) > 0.35

    blended = combine_quaternion_similarity(
        quat_sim=0.8,
        vec_sim=0.3,
        alpha_t=alpha_high,
        phase_d_enabled=True,
    )
    assert blended > 0.5
    assert blended <= 0.8
    # When disabled, the blend defaults to vector similarity
    disabled_score = combine_quaternion_similarity(
        quat_sim=0.8,
        vec_sim=0.3,
        alpha_t=alpha_high,
        phase_d_enabled=False,
    )
    assert disabled_score == 0.3


def test_phase_d_score_endpoint_smoke():
    client = TestClient(fastapi_app)
    payload = {
        "query_embedding": [1.0, 0.0, 0.0, 0.0],
        "episode_embeddings": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ],
        "enabled": True,
        "debug": True,
    }
    resp = client.post("/phase_d/score", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("scores"), list)
    assert len(data["scores"]) == len(payload["episode_embeddings"])
    assert data["diagnostics"]["phase_d"] is not None


def test_phase_d_score_batch_perf_smoke():
    from time import perf_counter

    from fram_serving.scoring._fractal_trace_scores_phase_d import phase_d_score_batch

    query = [0.1] * 32
    episodes = [[(i % 5) * 0.1 for _ in range(32)] for i in range(128)]
    start = perf_counter()
    result = phase_d_score_batch(
        query, episodes, phase_d_enabled=True, phase_d_debug=False
    )
    duration = perf_counter() - start

    assert len(result["scores"]) == len(episodes)
    assert duration < 0.5
