from __future__ import annotations

import runpy

import pytest


@pytest.mark.slow
def test_trace_probe_cli_runs(capsys):
    module = runpy.run_path("tools/trace_probe.py")
    exit_code = module["main"](["What is FRAM?", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out, "expected some output"
    # JSON contains decision field in summary
    assert "decision" in out
