import pytest
import glob
import json, os, subprocess, sys

THRESHOLD_F1 = float(os.environ.get("CALIB_F1_MIN", "0.15"))  # set via env if needed

def run(cmd):
    print(">>", " ".join(cmd))
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)

def test_phase_c_calibration_threshold():
    if not glob.glob("data/calib/*.jsonl"):
        pytest.skip("no local calibration tasks under data/calib (git-ignored)")
    # Ensure calibration artifacts exist by running the script
    run([sys.executable, "scripts/calibrate_phase_c.py",
         "--tasks", "data/calib/*.jsonl",
         "--out", "diag/phase_c_calib.json",
         "--csv", "diag/phase_c_calib.csv",
         "--md", "diag/phase_c_report.md",
         "--p-min", "0.0", "--r-min", "0.0", "--f1-min", "0.0"])  # gating off here; pytest asserts below

    with open("diag/phase_c_calib.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    agg = data.get("aggregate", {})
    f1 = float(agg.get("f1", 0.0))
    assert f1 >= THRESHOLD_F1, f"Macro F1 {f1:.4f} < threshold {THRESHOLD_F1:.4f}"
    fractal = data.get("fractal", {}).get("aggregate") if isinstance(data.get("fractal"), dict) else None
    assert fractal is not None, "Fractal summary missing from calibration output"
    assert fractal.get("count", 0) >= 1
