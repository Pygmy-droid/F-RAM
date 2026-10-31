from fram_eval.metrics import (
    as_of_accuracy,
    citation_precision_recall_f1,
    expected_calibration_error,
    latency_percentiles,
    mean_absolute_calibration_error,
    mean_reciprocal_rank,
    misrouting_rate,
    missed_evidence_rate,
    qa_exact_match,
    qa_token_f1,
    recall_at_k,
    reliability_curve,
    span_citation_correctness,
)


def test_reliability_curve_basic():
    preds = [0.1, 0.2, 0.8, 0.9]
    labels = [0, 0, 1, 1]
    bins = reliability_curve(preds, labels, n_bins=2)
    assert bins[0].count == 2
    assert bins[1].count == 2
    assert bins[1].accuracy == 1.0
    assert bins[1].confidence > 0.5


def test_calibration_errors_consistent():
    preds = [0.2, 0.4, 0.6, 0.9]
    labels = [0, 1, 0, 1]
    ece = expected_calibration_error(preds, labels, n_bins=2)
    mace = mean_absolute_calibration_error(preds, labels, n_bins=2)
    assert 0 <= ece <= 1
    assert 0 <= mace <= 1


def test_retrieval_and_route_metrics():
    rankings = [["noise", "right"], ["first"]]
    relevant = [("right",), ("first", "second")]
    assert recall_at_k(rankings[0], relevant[0], 1) == 0.0
    assert recall_at_k(rankings[0], relevant[0], 2) == 1.0
    assert mean_reciprocal_rank(rankings, relevant) == 0.75
    assert misrouting_rate(["local", "global"], ["local", "anchors"]) == 0.5
    assert missed_evidence_rate([True, False, True, False]) == 0.5


def test_answer_and_citation_metrics():
    assert qa_exact_match("The South!", "south") == 1.0
    assert qa_token_f1("south region", "the south") == 2 / 3

    ids = citation_precision_recall_f1(["a", "b"], ["b", "c"])
    assert ids == {"precision": 0.5, "recall": 0.5, "f1": 0.5}

    spans = span_citation_correctness([(0, 5), (4, 10)], [(5, 15)])
    assert spans["precision"] == 0.5
    assert spans["recall"] == 0.5
    assert spans["f1"] == 0.5


def test_efficiency_and_freshness_metrics():
    latencies = latency_percentiles([10.0, 20.0, 30.0, 40.0])
    assert 30.0 < latencies["p95_ms"] < 40.0
    assert latencies["p99_ms"] > latencies["p95_ms"]
    assert as_of_accuracy([True, False, True]) == 2 / 3
