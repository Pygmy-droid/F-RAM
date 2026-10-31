from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_refresh_docs_calibration_dry_run():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "tools" / "refresh_docs_calibration.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--hours", "0.01"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    stdout = result.stdout
    assert "list_recent_docs.py" in stdout
    assert "ingest_project_docs.py" in stdout
    assert "ingest_demo.py" in stdout
    assert "calibration_lint.py" in stdout
    assert "calibration_status.py" in stdout
