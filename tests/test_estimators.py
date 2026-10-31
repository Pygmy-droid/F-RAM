from fram_eval.estimators import EstimationInput, estimate_latency_and_memory


def test_estimator_scales_with_parameters():
    base = EstimationInput(k=8, L=4, m=2, r=8, prototypes=1000, dim=128)
    estimate = estimate_latency_and_memory(base)
    heavier = estimate_latency_and_memory(EstimationInput(k=base.k * 2, L=4, m=2, r=8, prototypes=1000, dim=128))
    assert heavier["latency_ms"] > estimate["latency_ms"]
    assert heavier["memory_mib"] == estimate["memory_mib"]
