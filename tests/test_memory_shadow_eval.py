from __future__ import annotations

from pathlib import Path

from fram_eval.conversation_memory_eval import build_eval_store
from fram_eval.memory_shadow_eval import evaluate_shadow
from fram_serving.config import FRAMConfig


def test_memory_shadow_eval_summary(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
            "probe_low_lex": "Recall the noon alpha event.",
        },
        {
            "id": "beta",
            "query": "Recall the beta event.",
            "answer": "Beta happened at dusk.",
            "probe": "Recall the beta event.",
            "probe_low_lex": "Which event happened at dusk?",
        },
    ]
    cfg = FRAMConfig()
    store, id_map, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    results, details, _ = evaluate_shadow(
        items,
        store=store,
        id_map=id_map,
        vectorizer=vectorizer,
        modes=("semantic", "lexical"),
        fields=("probe",),
        memory_k=1,
        k_values=(1, 3),
        include_details=True,
    )
    assert results["semantic"]["probe"]["count"] == 2.0
    assert results["lexical"]["probe"]["count"] == 2.0
    assert details is not None
    assert len(details["semantic"]["probe"]) == 2
