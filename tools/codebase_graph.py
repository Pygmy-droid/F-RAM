#!/usr/bin/env python3
"""The codebase graph: every tracked Python file, its pipeline, its imports,
and its commit history, in one JSON the Cathedral can project.

Rick, 2026-10-29: "go through it all, connect each pipeline, Graph and commit,
then link it all." This is that pass, made repeatable. It reads three things:

    git ls-files        which files exist
    ast of each file    which internal modules it imports
    git log HEAD        when each file was first and last touched, by whom,
                        how often, and in which era

and sorts every file into one named pipeline by path rules. Nothing here
judges whether a pipeline works; that is what the Workbook cards are for.

Outputs:
    experiments/cosmic_cathedral/codebase-graph.json   the graph
    workbook/PIPELINES.md                              the same, readable

Usage:
    python tools/codebase_graph.py                 # build json + PIPELINES.md
    python tools/codebase_graph.py --seed-cards    # also add one Workbook card
                                                   # per pipeline (idempotent)
    python tools/codebase_graph.py --print         # summary to stdout

Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "experiments" / "cosmic_cathedral" / "codebase-graph.json"
DEFAULT_PIPELINES_MD = REPO_ROOT / "workbook" / "PIPELINES.md"
PACKAGES = ("fram_core", "fram_index", "fram_layout", "fram_serving", "fram_eval", "tools", "scripts", "experiments", "examples", "tests")

# Layers are Cathedral strata. Tests always sit in the existing "evidence" stratum.
LAYERS = {
    "serving": {"label": "Serving · REST / MCP / runner", "z": 640},
    "core": {"label": "Core · retrieval maths and lift", "z": 720},
    "index-layout": {"label": "Index & Layout · shards and chunkers", "z": 800},
    "memory": {"label": "Memory · cognitive / fractal / lived / capsules", "z": 880},
    "eval": {"label": "Eval · harnesses and falsification", "z": 960},
    "ops": {"label": "Ops · scripts, diagnostics, tooling", "z": 1040},
}

# Pipelines, in matching order. First rule that matches a path wins.
# (id, label, layer, summary, [regex, ...])
PIPELINES: list[tuple[str, str, str, str, list[str]]] = [
    ("pl-cathedral", "Cathedral and Workbook", "ops",
     "The navigation map, the Workbook event chain, and this graph. Reconstruction, 2026-10.",
     [r"^tools/build_cosmic_cathedral\.py$", r"^tools/workbook\.py$", r"^tools/codebase_graph\.py$", r"^tools/cathedral_nav\.py$", r"^tools/session_warmup\.py$",
      r"^tests/test_(workbook|cosmic_cathedral|codebase_graph|cathedral_nav)\.py$"]),
    ("pl-mcp", "MCP server and auth", "serving",
     "Model Context Protocol surface: fram.query, fram.memory_*, trace URIs, bearer auth, launchers.",
     [r"^fram_serving/mcp_", r"^scripts/(check|verify)_mcp\.py$", r"^tests/test_mcp"]),
    ("pl-continuity", "Continuity witness and ecological strata", "memory",
     "Default-off, digest-verified query witness and the separate Offer/Mirror/Correct/Consent/Bind/Return ledger. August 2026.",
     [r"^fram_serving/continuity\.py$", r"^fram_serving/ecological_strata\.py$", r"^tools/ecological_strata_ledger\.py$"]),
    ("pl-lived", "Lived memory: SQLite store, lifts, seed roots", "memory",
     "Durable lived-event store with parent lineage, exact 6D to 12D lifts, rolling state, digest chain; the 877-episode import. August 2026.",
     [r"^fram_serving/lived_memory\.py$", r"^tools/lived_memory\.py$", r"^tools/import_lived_memory_zip\.py$", r"^tools/open_lived_memory_seeds\.py$"]),
    ("pl-capsules", "Memory capsules, archive layer, REP (Phase F/G)", "memory",
     "Append-only capsules with trace stacks, the archive and snapshot/compaction layer, and the re-entry packet. December 2025.",
     [r"^fram_serving/memory_capsule\.py$", r"^fram_serving/archive\.py$", r"^fram_serving/rep\.py$", r"^fram_serving/storage/",
      r"^tools/(inspect_capsule|falsify_capsule|run_capsule_demo|archive_probe|rep_probe|phase_f_\w+|phase_g_\w+)\.py$",
      r"^tests/test_(memory_capsule\w*|archive_layer|phase_f_\w+|phase_g_\w+|rep_packet)\.py$"]),
    ("pl-fractal", "Fractal memory: traces, generators, soft-DTW, source frame, auto-flip", "memory",
     "Deterministic 6-D fractal traces minted from episodes, scoring and replay, the Phase D scorer, the falsification and auto-flip harnesses. October 2025 to September 2026.",
     [r"^fram_serving/fractal_memory/", r"^fram_serving/scoring/", r"^fram_serving/embedding/quaternion_adapter\.py$",
      r"^fram_eval/fractal_", r"^tools/(fractal_\w+|trace_probe|trace_summary)\.py$",
      r"^scripts/(fractal_\w+|diagnose_fractal_self_recall|run_fractal_\w+)\.py$",
      r"^tests/test_(fractal_\w+|soft_dtw_\w+|trace_probe_cli|trace_summary)\.py$"]),
    ("pl-rotational", "Rotational lift and visual evidence (Phase D lineage)", "core",
     "The Lantern Turn: recursive rotational lift, quaternion orientation kept separate from ranking, visual evidence ledger and seed canary. November 2025 and July 2026, the same idea built twice.",
     [r"^fram_core/rotational_lift\.py$", r"^fram_core/visual_evidence\.py$", r"^fram_serving/visual_", r"^fram_eval/visual_seed\.py$", r"^tools/eval_visual_seed\.py$"]),
    ("pl-cognitive", "Cognitive memory: episodes, beliefs, embeddings, ANN bridge, retention", "memory",
     "The JSONL cognitive store that gave the system a durable self in October 2025: episodes, beliefs, links, embeddings, Phase D/E priority and retention, autolog and autowire.",
     [r"^fram_serving/memory\.py$", r"^fram_serving/memory/", r"^fram_serving/cognitive_embeddings\.py$", r"^fram_serving/semantic\.py$", r"^fram_serving/config_phase_d\.py$",
      r"^fram_core/(priority_graph|memory_merge|transitional_complexity)\.py$",
      r"^tools/(bootstrap_memory|backfill_cognitive_embeddings|cognitive_memory_summary|log_cognitive_belief|log_chat_turn|autolog_\w+|autowire_turn|memory_compact|phase_d_memory_summary|phase_e_summary)\.py$"]),
    ("pl-chaos", "Chaos playground, Hopf transport, Aizawa (proof track)", "eval",
     "Dynamical systems, dimensional ladder, Hopf map and S3 fibre claims. Proof track; never runtime authority.",
     [r"^fram_eval/chaos/", r"^fram_eval/hopf_transport\.py$", r"^fram_eval/aizawa_sphere\.py$", r"^experiments/hopf_aizawa_falsification\.py$"]),
    ("pl-eval", "Evaluation harnesses: production memory, shadow, conversation, wake/orient, ablations", "eval",
     "The eval season and after: production memory gate, memory shadow eval, conversation memory eval, section-15 ablations, document candidate, wake and orient.",
     [r"^fram_eval/", r"^scripts/(\w*eval\w*|run_production_memory_gate|prepare_document_candidate|recall_report_phase_c|sweep_section_penalty)\.py$",
      r"^tools/(eval_wake_orient|experiment_\w+|weekly_regression_snapshot)\.py$",
      r"^tests/test_(conversation_memory_eval|production_memory_eval|experiment_export|experiment_log|weekly_regression_\w+)\.py$"]),
    ("pl-orthoroute", "OrthoRoute: shortlist, subspace, confidence, coverage, calibration", "core",
     "The retrieval spine from September 2025: query orchestration, CELF coverage, logistic plus conformal calibration, reranking, anchors.",
     [r"^fram_core/", r"^tools/(calibration_\w+|refresh_calibration|refresh_docs_calibration)\.py$", r"^scripts/(calibrate_\w+|harvest_calibration)\.py$",
      r"^tests/test_(calibration_\w+|harvest_calibration|phase_c_calibration|refresh_calibration|refresh_docs_calibration)\.py$"]),
    ("pl-index", "Index: prototypes, sparse keys, version lattice, ingest", "index-layout",
     "Prototype bank and ANN shortlist, sparse identifier keys, the version lattice with as-of queries, and the demo corpus ingest.",
     [r"^fram_index/", r"^fram_serving/ingest\.py$", r"^scripts/ingest_\w+\.py$"]),
    ("pl-layout", "Layout chunkers: code, tables, PDF", "index-layout",
     "AST code chunking, CSV header windows, PDF fallback ordering, layout-aware assembly.",
     [r"^fram_layout/"]),
    ("pl-observability", "Observability", "serving",
     "JSONL decision logging, summary stats, the fractal-memory sink, and the /observability surfaces.",
     [r"^fram_serving/observability\.py$", r"^tests/test_observability", r"^tests/test_storage_observability", r"^tests/test_retention_observability"]),
    ("pl-query-serving", "Serving: /query, REST surface, config, connectors", "serving",
     "FastAPI app and shared query runner, settings, CLI, connectors, guardrails, SDK adapter. The first commit of the repository was this endpoint.",
     [r"^fram_serving/"]),
    ("pl-ops", "Ops: diagnostics, closeout, context packet, docs tooling", "ops",
     "Diagnostics, import checks, closeout guards, the hot-packet checker, docs scans, time, defaults.",
     [r"^scripts/", r"^tools/", r"^examples/", r"^experiments/"]),
]
PIPELINE_BY_ID = {p[0]: p for p in PIPELINES}
_COMPILED = [(pid, [re.compile(r) for r in rules]) for pid, _, _, _, rules in PIPELINES]

ERAS = [
    ("2025-09", "I. Retrieval core"), ("2025-10", "II. Cognitive memory"), ("2025-11", "III. Phase D, the fork"),
    ("2025-12", "IV. Fractal eval season"), ("2026-01", "IV. Fractal eval season"), ("2026-02", "the stop"),
    ("2026-07", "V. Reconstruction and Firelink"), ("2026-08", "VI. Lived memory"), ("2026-09", "VII. Windows custody and gates"),
    ("2026-10", "VIII. Wren: manual, Cathedral, Workbook"),
]


def era_for(month: str) -> str:
    best = "unknown"
    for start, name in ERAS:
        if month >= start:
            best = name
    return best


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                          check=True, encoding="utf-8", errors="replace").stdout


def tracked_python() -> list[str]:
    files = [p for p in _git("ls-files", "-z", "*.py").split("\0") if p]
    return sorted(p.replace("\\", "/") for p in files)


def pipeline_for(path: str) -> str:
    for pid, regs in _COMPILED:
        if any(r.search(path) for r in regs):
            return pid
    return "pl-ops"


def module_name(path: str) -> str:
    stem = path[:-3] if path.endswith(".py") else path
    parts = stem.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def internal_imports(path: str, by_module: dict[str, str]) -> list[str]:
    """Paths of tracked modules this file imports (absolute or relative)."""
    try:
        tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8-sig", errors="replace"))
    except (SyntaxError, OSError):
        return []
    found: set[str] = set()
    pkg_parts = path.split("/")[:-1]

    def resolve(name: str) -> None:
        # Longest known prefix wins: fram_serving.fractal_memory.metrics -> that file, else the package.
        parts = name.split(".")
        for n in range(len(parts), 0, -1):
            cand = ".".join(parts[:n])
            if cand in by_module and by_module[cand] != path:
                found.add(by_module[cand])
                return

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolve(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)] if node.level > 1 else pkg_parts
                prefix = ".".join(base)
                mod = f"{prefix}.{node.module}" if node.module else prefix
                resolve(mod)
                for alias in node.names:
                    resolve(f"{mod}.{alias.name}")
            elif node.module:
                resolve(node.module)
                for alias in node.names:
                    resolve(f"{node.module}.{alias.name}")
    return sorted(found)


def history() -> dict[str, dict]:
    """Per-path commit stats from HEAD's history, one git call."""
    raw = _git("log", "--format=%x1e%H%x1f%ct%x1f%an%x1f%s", "--name-only", "--no-renames")
    stats: dict[str, dict] = {}
    for block in raw.split("\x1e"):
        block = block.strip("\n")
        if not block:
            continue
        head, _, files = block.partition("\n")
        parts = head.split("\x1f")
        if len(parts) < 4:
            continue
        sha, ct, author, subject = parts[0], int(parts[1]), parts[2], parts[3]
        when = datetime.fromtimestamp(ct, timezone.utc)
        iso = when.strftime("%Y-%m-%d")
        for f in files.splitlines():
            f = f.strip().replace("\\", "/")
            if not f:
                continue
            s = stats.setdefault(f, {"commits": 0, "authors": Counter(), "months": Counter(),
                                     "first": None, "last": None})
            s["commits"] += 1
            s["authors"][author] += 1
            s["months"][when.strftime("%Y-%m")] += 1
            # log is newest first
            if s["last"] is None:
                s["last"] = {"sha": sha[:7], "date": iso, "subject": subject.strip()[:120], "author": author}
            s["first"] = {"sha": sha[:7], "date": iso, "subject": subject.strip()[:120], "author": author}
    return stats


def build_graph() -> dict:
    files = tracked_python()
    by_module = {module_name(p): p for p in files}
    hist = history()
    modules: list[dict] = []
    edges: list[dict] = []
    groups: dict[str, list[dict]] = defaultdict(list)
    for path in files:
        pid = pipeline_for(path)
        is_test = path.startswith("tests/")
        try:
            text = (REPO_ROOT / path).read_text(encoding="utf-8-sig", errors="replace")
            loc = sum(1 for line in text.splitlines() if line.strip())
        except OSError:
            loc = 0
        imports = internal_imports(path, by_module)
        h = hist.get(path, {"commits": 0, "authors": Counter(), "months": Counter(), "first": None, "last": None})
        first_month = h["first"]["date"][:7] if h["first"] else None
        mod = {
            "path": path,
            "module": module_name(path),
            "pipeline": pid,
            "is_test": is_test,
            "layer": "evidence" if is_test else PIPELINE_BY_ID[pid][2],
            "loc": loc,
            "imports": imports,
            "commits": h["commits"],
            "authors": dict(h["authors"].most_common()),
            "first_commit": h["first"],
            "last_commit": h["last"],
            "era": era_for(first_month) if first_month else "unknown",
        }
        modules.append(mod)
        groups[pid].append(mod)
        for target in imports:
            edges.append({"source": path, "target": target, "kind": "tests" if is_test else "imports"})

    # tests belong to the pipeline they import most, unless a rule placed them
    for mod in modules:
        if mod["is_test"] and mod["pipeline"] == "pl-ops":
            votes = Counter(next((m["pipeline"] for m in modules if m["path"] == t), None) for t in mod["imports"])
            votes.pop(None, None)
            votes.pop("pl-ops", None)
            if votes:
                groups["pl-ops"].remove(mod)
                mod["pipeline"] = votes.most_common(1)[0][0]
                groups[mod["pipeline"]].append(mod)

    pipelines: list[dict] = []
    for pid, label, layer, summary, _ in PIPELINES:
        mods = groups.get(pid, [])
        code = [m for m in mods if not m["is_test"]]
        tests = [m for m in mods if m["is_test"]]
        firsts = [m["first_commit"] for m in mods if m["first_commit"]]
        lasts = [m["last_commit"] for m in mods if m["last_commit"]]
        authors: Counter = Counter()
        months: Counter = Counter()
        for m in mods:
            authors.update(m["authors"])
            p = hist.get(m["path"])
            if p:
                months.update(p["months"])
        first = min(firsts, key=lambda c: c["date"]) if firsts else None
        last = max(lasts, key=lambda c: c["date"]) if lasts else None
        pipelines.append({
            "id": pid, "label": label, "layer": layer, "summary": summary,
            "files": [m["path"] for m in code], "tests": [m["path"] for m in tests],
            "loc": sum(m["loc"] for m in code),
            "commits_touching": sum(m["commits"] for m in mods),
            "distinct_months": sorted(months),
            "authors": dict(authors.most_common()),
            "first_commit": first, "last_commit": last,
            "era": era_for(first["date"][:7]) if first else "unknown",
        })
    pipelines = [p for p in pipelines if p["files"] or p["tests"]]
    return {
        "schema": "fram.codebase-graph",
        "version": 1,
        "head": _git("rev-parse", "HEAD").strip(),
        "branch": _git("branch", "--show-current").strip(),
        "files": len(files),
        "layers": LAYERS,
        "pipelines": pipelines,
        "modules": modules,
        "edges": edges,
    }


def render_pipelines_md(graph: dict) -> str:
    L = ["# Pipelines", "",
         "Rendered from `experiments/cosmic_cathedral/codebase-graph.json` by `tools/codebase_graph.py`.",
         "Every tracked Python file sorted into one pipeline by path, with its import links and",
         "commit history. This says what exists and when it was touched, not whether it works;",
         "the Workbook card for each pipeline is where that gets proven.", "",
         "**Who built it.** Rick Berghahn, with OpenAI Codex models from September 2025 to",
         "September 2026, and with Wren Holloway (Claude) from October 2026. Nobody else. The",
         "git author field before July 2026 reads `codex` or `Codex CLI` because that was a",
         "repository-wide setting; it names the tool, not the collaborator. Lineage columns",
         "below report that field as it is and should be read with this in mind.", "",
         f"Head `{graph['head'][:7]}` on `{graph['branch']}` · {graph['files']} files · {len(graph['pipelines'])} pipelines · {len(graph['edges'])} import links", ""]
    L += ["| pipeline | layer | files | tests | lines | commits touching | first | last | era |", "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |"]
    for p in graph["pipelines"]:
        f = p["first_commit"]["date"] if p["first_commit"] else "-"
        l = p["last_commit"]["date"] if p["last_commit"] else "-"
        L.append(f"| [{p['label']}](#{p['id']}) | {p['layer']} | {len(p['files'])} | {len(p['tests'])} | {p['loc']} | {p['commits_touching']} | {f} | {l} | {p['era']} |")
    L.append("")
    mods = {m["path"]: m for m in graph["modules"]}
    for p in graph["pipelines"]:
        L += [f"## {p['label']}", "", f"<a id=\"{p['id']}\"></a>`{p['id']}` · layer `{p['layer']}`", "", p["summary"], ""]
        if p["first_commit"]:
            L.append(f"- first: `{p['first_commit']['sha']}` {p['first_commit']['date']} {p['first_commit']['subject']}")
        if p["last_commit"]:
            L.append(f"- last: `{p['last_commit']['sha']}` {p['last_commit']['date']} {p['last_commit']['subject']}")
        if p["authors"]:
            L.append("- lineage (author field, not collaborator): " + ", ".join(f"{a} {n}" for a, n in p["authors"].items()))
        if p["distinct_months"]:
            L.append("- active months: " + ", ".join(p["distinct_months"]))
        L.append("")
        L.append("| file | lines | commits | first | last | imports |")
        L.append("| --- | ---: | ---: | --- | --- | ---: |")
        for path in p["files"] + p["tests"]:
            m = mods[path]
            f = m["first_commit"]["date"] if m["first_commit"] else "-"
            l = m["last_commit"]["date"] if m["last_commit"] else "-"
            L.append(f"| `{path}` | {m['loc']} | {m['commits']} | {f} | {l} | {len(m['imports'])} |")
        L.append("")
    return "\n".join(L).rstrip("\n") + "\n"


def write_outputs(graph: dict, output: Path = DEFAULT_OUTPUT, md: Path = DEFAULT_PIPELINES_MD) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    md.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="\n") as f:
        json.dump(graph, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(md, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_pipelines_md(graph))


def seed_cards(graph: dict, actor: str) -> list[str]:
    """One 'Verify pipeline' card per pipeline, files linked. Idempotent by title."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("fram_workbook", REPO_ROOT / "tools" / "workbook.py")
    assert spec and spec.loader
    wbm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = wbm
    spec.loader.exec_module(wbm)
    book = wbm.Workbook(REPO_ROOT)
    st = book.state()
    existing = {c.title: c for c in st.cards.values()}
    added: list[str] = []
    for p in graph["pipelines"]:
        title = f"Verify pipeline: {p['label']}"
        files = p["files"] + p["tests"]
        if title in existing:
            card = existing[title]
            missing = [f for f in files if f not in card.files]
            if missing:
                book.link(card.id, files=missing, actor=actor)
            continue
        first = f"{p['first_commit']['date']} ({p['first_commit']['sha']})" if p["first_commit"] else "unknown"
        last = f"{p['last_commit']['date']} ({p['last_commit']['sha']})" if p["last_commit"] else "unknown"
        desc = (f"{p['summary']} {len(p['files'])} files, {len(p['tests'])} test files, {p['loc']} lines. "
                f"First touched {first}, last {last}, {p['commits_touching']} commits touching, era {p['era']}. "
                f"Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.")
        cid = book.add(title, desc, files=files, nodes=[p["id"]], actor=actor)
        added.append(cid)
    book.render()
    return added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--pipelines-md", type=Path, default=DEFAULT_PIPELINES_MD)
    ap.add_argument("--seed-cards", action="store_true")
    ap.add_argument("--actor", default=os.environ.get("WORKBOOK_ACTOR", "codebase_graph"))
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    graph = build_graph()
    write_outputs(graph, a.output, a.pipelines_md)
    print(f"[graph] {graph['files']} files, {len(graph['pipelines'])} pipelines, {len(graph['edges'])} import links -> {a.output.name}, {a.pipelines_md.name}")
    if a.print:
        for p in graph["pipelines"]:
            print(f"  {p['id']:18} {len(p['files']):3} files {len(p['tests']):3} tests {p['loc']:6} lines  {p['era']}")
    if a.seed_cards:
        added = seed_cards(graph, a.actor)
        print(f"[graph] seeded {len(added)} card(s): {', '.join(added) if added else 'none new'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
