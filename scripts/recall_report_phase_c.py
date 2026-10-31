#!/usr/bin/env python3
"""
Phase C recall report — reads diag/phase_c_calib.json and prints a compact summary.
"""
import json, os, sys

def main():
    path = "diag/phase_c_calib.json"
    if not os.path.exists(path):
        print("[recall_report_phase_c] missing diag/phase_c_calib.json; run calibrate first.", file=sys.stderr)
        sys.exit(2)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    agg = data.get("aggregate", {})
    rows = data.get("per_task", [])
    fractal_info = data.get("fractal") if isinstance(data.get("fractal"), dict) else None
    fractal_agg = None
    if fractal_info:
        maybe_agg = fractal_info.get("aggregate")
        if isinstance(maybe_agg, dict) and maybe_agg.get("count"):
            fractal_agg = maybe_agg
    # Show top 10 worst F1 tasks to guide fixes
    worst = sorted(rows, key=lambda r: r.get("f1", 0.0))[:10]

    print("=== Phase C Recall Report ===")
    print(f"Tasks: {agg.get('count',0)}")
    print(f"Macro Precision: {agg.get('precision',0.0)}")
    print(f"Macro Recall:    {agg.get('recall',0.0)}")
    print(f"Macro F1:        {agg.get('f1',0.0)}")
    if fractal_agg:
        print("\nFractal Macro Metrics:")
        print(f"- Precision: {fractal_agg.get('precision', 0.0)}")
        print(f"- Recall:    {fractal_agg.get('recall', 0.0)}")
        print(f"- F1:        {fractal_agg.get('f1', 0.0)}")
    print("\nWorst 10 by F1:")
    for r in worst:
        rid = r.get("id","<unknown>")
        print(f"- {rid}: P={r.get('precision',0.0)} R={r.get('recall',0.0)} F1={r.get('f1',0.0)} "
              f"(exp={r.get('expected_count',0)} ret={r.get('retrieved_count',0)})")
        if fractal_agg and "fractal_f1" in r:
            print(
                f"    fractal: P={r.get('fractal_precision',0.0)} "
                f"R={r.get('fractal_recall',0.0)} F1={r.get('fractal_f1',0.0)} "
                f"(count={r.get('fractal_count',0)})"
            )

if __name__ == "__main__":
    main()
