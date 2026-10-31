from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

import fram_serving.app as app_mod


def _coerce_storage_root(root: Optional[str]) -> None:
    if not root:
        return
    base = Path(root)
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": base})
    # Point app at new storage and rebuild orchestrator/cog store lazily
    app_mod.CFG = cfg  # type: ignore[assignment]
    try:
        app_mod._ORCHESTRATOR = None  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        app_mod._COG_STORE = app_mod.CognitiveMemoryStore(
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
            config=cfg,
        )
    except Exception:
        pass


def _summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    answer = payload.get("answer", "")
    citations = payload.get("citations") or []
    trace = payload.get("trace", {})
    conf = trace.get("confidence", {}) if isinstance(trace, dict) else {}
    calib = conf.get("calibration", {}) if isinstance(conf, dict) else {}
    selection = trace.get("selection", {}) if isinstance(trace, dict) else {}
    summary = {
        "query": trace.get("query"),
        "domain": trace.get("domain"),
        "task": trace.get("task"),
        "decision": conf.get("decision"),
        "p_temp": trace.get("p_temp"),
        "calibration": {
            "source": calib.get("source"),
            "tau1": calib.get("tau1"),
            "tau2": calib.get("tau2"),
            "temperature": calib.get("temperature"),
        },
        "coverage_delta": selection.get("coverage_delta", {}),
        "budgets": selection.get("budgets", {}),
        "celf_stats": selection.get("celf_stats", {}),
        "citations_count": len(citations) if isinstance(citations, list) else 0,
        "answer_preview": (answer or "")[:200],
    }
    cog = (trace.get("cognitive_memory") or {}) if isinstance(trace, dict) else {}
    if cog:
        selected = cog.get("selected") or []
        summary["cognitive_memory"] = {
            "selected_ids": [s.get("id") for s in selected if isinstance(s, dict)],
            "selected_count": len(selected),
            "token_budget": cog.get("token_budget"),
        }
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Quick trace probe for /query")
    parser.add_argument("text", help="Query text to probe")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--task", default=None)
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--memory-session", dest="memory_session", default=None)
    parser.add_argument("--storage-root", dest="storage_root", default=None, help="Override storage root path")
    parser.add_argument("--json", action="store_true", help="Emit full JSON summary")
    args = parser.parse_args(argv)

    _coerce_storage_root(args.storage_root)

    with TestClient(app_mod.app) as client:
        body = {"text": args.text}
        if args.as_of:
            body["as_of"] = args.as_of
        if args.domain:
            body["domain"] = args.domain
        if args.task:
            body["task"] = args.task
        if args.memory_session:
            body["memory_session"] = args.memory_session
        resp = client.post("/query", json=body)
        if resp.status_code != 200:
            sys.stderr.write(f"/query failed: {resp.status_code} {resp.text}\n")
            return 2
        data = resp.json()
        summary = _summarize(data)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False))
        else:
            line = (
                f"decision={summary.get('decision')} p_temp={summary.get('p_temp')} "
                f"calib={summary.get('calibration', {}).get('source')} "
                f"tau1={summary.get('calibration', {}).get('tau1')} tau2={summary.get('calibration', {}).get('tau2')} "
                f"citations={summary.get('citations_count')}"
            )
            cog = summary.get("cognitive_memory") or {}
            if cog:
                line += f" cog_selected={cog.get('selected_count')}"
            print(line)
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
