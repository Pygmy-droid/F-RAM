from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.fractal_falsification import merge_payloads


def _write_payload(path: Path, seed: int, system: str) -> None:
    payload = {
        "config": {"seed": seed, "count": 1},
        "systems": {
            system: {
                "classic": {
                    "baseline": {
                        "pairs": 1.0,
                        "spearman_rho": 0.1,
                        "top1": 0.5,
                        "top3": 1.0,
                    },
                    "ablations": {},
                }
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_merge_payloads(tmp_path: Path) -> None:
    p1 = tmp_path / "logistic.json"
    p2 = tmp_path / "henon.json"
    _write_payload(p1, seed=1, system="logistic")
    _write_payload(p2, seed=2, system="henon")

    merged = merge_payloads([p1, p2])
    seed_runs = merged["seed_runs"]
    assert "1" in seed_runs and "2" in seed_runs
    assert "logistic" in seed_runs["1"]
    assert "henon" in seed_runs["2"]
    aggregate = merged["aggregate"]
    assert "logistic" in aggregate
    assert "henon" in aggregate


def test_fractal_falsification_cli_runs_directly_and_advertises_aizawa() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "fractal_falsification.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "aizawa" in result.stdout
