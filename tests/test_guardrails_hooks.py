from __future__ import annotations

from fram_serving.guardrails import hooks


def test_guardrails_allow_by_default():
    allowed, reason = hooks.before_memory_write({})
    assert allowed is True
    assert reason is None


def test_guardrails_record_block():
    hooks.record_block("write", "deny")
    last = hooks.last_block()
    assert last and last["hook"] == "write" and last["reason"] == "deny"
