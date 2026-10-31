from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_refresh_calibration_dry_run():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "refresh_calibration.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    stdout = result.stdout
    assert "harvest_calibration.py" in stdout
    assert "calibration_backfill.py" in stdout
    assert "calibrate_confidence.py" in stdout
    assert "calibration_lint.py" in stdout
    assert "calibration_status.py" in stdout
