#!/usr/bin/env python3
"""
Phase C calibration — simple, useful metrics.

Input format (JSONL under data/calib/*.jsonl):
{
  "id": "task-001",
  "query": "example query",
  "expected_ids": ["docA","docB","docC"],   # relevant items
  "retrieved_ids": ["docB","docX","docC"]   # system output (order ignored here)
}

Outputs:
- diag/phase_c_calib.json (aggregate + per-task metrics)
- diag/phase_c_report.md (markdown summary; override via --md)
"""

import argparse, glob, json, os, sys, csv, datetime
from typing import List, Dict, Any, Tuple, Optional

def prf1(expected: List[str], retrieved: List[str]) -> Tuple[float, float, float]:
    exp = set(expected or [])
    ret = set(retrieved or [])
    tp = len(exp & ret)
    fp = len(ret - exp)
    fn = len(exp - ret)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1

def load_tasks(patterns: List[str]) -> List[Dict[str, Any]]:
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    tasks = []
    for path in sorted(files):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tasks.append(json.loads(line))
                except Exception as e:
                    tasks.append({"_parse_error": str(e), "_raw": line, "_file": path})
    return tasks

def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"count": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    p = sum(r["precision"] for r in rows) / len(rows)
    r = sum(r["recall"] for r in rows) / len(rows)
    f = sum(r["f1"] for r in rows) / len(rows)
    return {"count": len(rows), "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=["data/calib/*.jsonl"], help="Glob(s) to JSONL tasks")
    ap.add_argument("--out", default="diag/phase_c_calib.json")
    ap.add_argument("--csv", default="diag/phase_c_calib.csv")
    ap.add_argument("--md", default="diag/phase_c_report.md")
    ap.add_argument("--fractal-field", default="fractal_ids", help="Optional JSON field carrying fractal recall IDs")
    ap.add_argument("--p-min", type=float, default=None, help="Fail if macro precision < this")
    ap.add_argument("--r-min", type=float, default=None, help="Fail if macro recall < this")
    ap.add_argument("--f1-min", type=float, default=None, help="Fail if macro F1 < this")
    ap.add_argument("--fractal-p-min", type=float, default=None, help="Fail if fractal precision < this")
    ap.add_argument("--fractal-r-min", type=float, default=None, help="Fail if fractal recall < this")
    ap.add_argument("--fractal-f1-min", type=float, default=None, help="Fail if fractal F1 < this")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tasks = load_tasks(args.tasks)

    per_task = []
    fractal_rows: List[Dict[str, float]] = []
    fractal_field = (args.fractal_field or "").strip()
    for t in tasks:
        if "_parse_error" in t:
            per_task.append({
                "id": t.get("id") or t.get("_file","<unknown>"),
                "precision": 0.0, "recall": 0.0, "f1": 0.0,
                "error": t["_parse_error"],
            })
            continue
        expected = t.get("expected_ids", [])
        retrieved = t.get("retrieved_ids", [])
        p,r,f = prf1(expected, retrieved)
        entry: Dict[str, Any] = {
            "id": t.get("id") or t.get("query","<no-id>"),
            "precision": round(p,4),
            "recall": round(r,4),
            "f1": round(f,4),
            "expected_count": len(expected),
            "retrieved_count": len(retrieved),
        }
        fractal_values: Optional[List[str]] = None
        if fractal_field:
            field_value = t.get(fractal_field)
            if isinstance(field_value, list):
                fractal_values = [str(x) for x in field_value]
        if fractal_values is not None:
            fp, fr, ff = prf1(expected, fractal_values)
            entry.update({
                "fractal_precision": round(fp, 4),
                "fractal_recall": round(fr, 4),
                "fractal_f1": round(ff, 4),
                "fractal_count": len(fractal_values),
            })
            fractal_rows.append({
                "precision": entry["fractal_precision"],
                "recall": entry["fractal_recall"],
                "f1": entry["fractal_f1"],
            })
        per_task.append(entry)

    agg = aggregate(per_task)
    fractal_agg = aggregate(fractal_rows) if fractal_rows else None
    out = {
        "ok": True,
        "meta": {
            "task_globs": args.tasks,
            "fractal_field": fractal_field or None,
        },
        "aggregate": agg,
        "per_task": per_task,
    }
    if fractal_agg:
        out["fractal"] = {"aggregate": fractal_agg}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[calibrate_phase_c] wrote {args.out}")
    print(json.dumps(agg, indent=2))

    # CSV dump for spreadsheet/plots
    with open(args.csv, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        header = [
            "id","precision","recall","f1","expected_count","retrieved_count",
        ]
        if fractal_rows:
            header.extend(["fractal_precision","fractal_recall","fractal_f1","fractal_count"])
        w.writerow(header)
        for r in per_task:
            row = [
                r.get("id"),
                r.get("precision"),
                r.get("recall"),
                r.get("f1"),
                r.get("expected_count",0),
                r.get("retrieved_count",0),
            ]
            if fractal_rows:
                row.extend([
                    r.get("fractal_precision",""),
                    r.get("fractal_recall",""),
                    r.get("fractal_f1",""),
                    r.get("fractal_count",""),
                ])
            w.writerow(row)
    print(f"[calibrate_phase_c] wrote {args.csv}")

    # Markdown summary (macro + worst offenders)
    os.makedirs(os.path.dirname(args.md), exist_ok=True)
    worst = sorted(per_task, key=lambda r: r.get("f1", 0.0))[:10]
    now = datetime.datetime.utcnow().isoformat() + "Z"
    with open(args.md, "w", encoding="utf-8") as mf:
        mf.write("# Phase C - Calibration Report\n\n")
        mf.write(f"_Generated: {now}_\n\n")
        mf.write("## Macro Metrics\n")
        mf.write(f"- Precision: **{agg['precision']}**\n")
        mf.write(f"- Recall: **{agg['recall']}**\n")
        mf.write(f"- F1: **{agg['f1']}**\n\n")
        if fractal_agg:
            mf.write("## Fractal Recall Metrics\n")
            mf.write(f"- Precision: **{fractal_agg['precision']}**\n")
            mf.write(f"- Recall: **{fractal_agg['recall']}**\n")
            mf.write(f"- F1: **{fractal_agg['f1']}**\n\n")
        mf.write("## Worst 10 by F1\n\n")
        if fractal_rows:
            mf.write("| id | P | R | F1 | exp | ret | F_P | F_R | F1_F |\n")
            mf.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        else:
            mf.write("| id | P | R | F1 | exp | ret |\n|---|---:|---:|---:|---:|---:|\n")
        for r in worst:
            base_row = (
                f"| {r.get('id')} | {r.get('precision',0)} | {r.get('recall',0)} | {r.get('f1',0)} | "
                f"{r.get('expected_count',0)} | {r.get('retrieved_count',0)}"
            )
            if fractal_rows:
                base_row += (
                    f" | {r.get('fractal_precision','-')} | {r.get('fractal_recall','-')} | {r.get('fractal_f1','-')} |"
                )
            else:
                base_row += " |"
            mf.write(base_row + "\n")
        mf.write("\n")
    print(f"[calibrate_phase_c] wrote {args.md}")

    # Threshold gating
    fail = []
    if args.p_min is not None and agg["precision"] < args.p_min: fail.append(f"precision<{args.p_min}")
    if args.r_min is not None and agg["recall"]    < args.r_min: fail.append(f"recall<{args.r_min}")
    if args.f1_min is not None and agg["f1"]       < args.f1_min: fail.append(f"f1<{args.f1_min}")
    if fractal_agg:
        if args.fractal_p_min is not None and fractal_agg["precision"] < args.fractal_p_min:
            fail.append(f"fractal_precision<{args.fractal_p_min}")
        if args.fractal_r_min is not None and fractal_agg["recall"] < args.fractal_r_min:
            fail.append(f"fractal_recall<{args.fractal_r_min}")
        if args.fractal_f1_min is not None and fractal_agg["f1"] < args.fractal_f1_min:
            fail.append(f"fractal_f1<{args.fractal_f1_min}")
    if fail:
        print("[calibrate_phase_c] FAIL:", ", ".join(fail), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
