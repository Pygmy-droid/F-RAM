from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_phase_e_summary_cli_outputs_fields(tmp_path):
    script = Path(__file__).resolve().parents[1] / "tools" / "phase_e_summary.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=True,
    )
    out = proc.stdout.lower()
    assert "retention_half_life_days" in out
    assert "forgetting_half_life_days" in out
    assert "forgetting_threshold" in out
    assert "forget_score" in out
