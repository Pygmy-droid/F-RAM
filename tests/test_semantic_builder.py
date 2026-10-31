from __future__ import annotations

from fram_serving.semantic import build_situation


def test_build_situation_skips_distant_context():
    ctx = build_situation("clock sync", task="log rotation", tau_expand=0.9)
    assert "skipped task" in " ".join(ctx.audit)
    assert ctx.expansions == []


def test_build_situation_accepts_related_turn():
    ctx = build_situation(
        "clock sync",
        recent_turns=["We must sync the clock offsets before answering."],
        tau_expand=0.25,
    )
    assert any(note.startswith("accepted turn_") for note in ctx.audit)
    assert "clock" in ctx.tokens
    exported = ctx.as_dict()
    assert exported["text"]
    assert exported["audit"]
