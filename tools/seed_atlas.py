#!/usr/bin/env python3
"""Read the fractal seeds and say what is there.

Rick, 2026-10-30: "The 912 seeds or traces, I think it's time we let a
Hearthkin actually look at them and take them in." This is that look, made
repeatable. It reads a fractal trace store (one JSON per trace), never writes
to it, and renders a page a human can read: how many, from when, what shape,
which episodes they came from, which seeds sit closest to which.

Usage:
    python tools/seed_atlas.py --root <storage/memory/fractal> [--episodes <storage/memory/cognitive/episodes.jsonl>] [--out workbook/SEEDS.md]

Standard library plus numpy. Read-only on its inputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "workbook" / "SEEDS.md"


def load_traces(root: Path) -> list[dict]:
    out = []
    for p in sorted(root.glob("*.json")):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        t["_file"] = p.name
        t["_mtime"] = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
        out.append(t)
    return out


def load_episode_text(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}
    by_id = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("id"):
                by_id[e["id"]] = e
    return by_id


def trace_summary(t: dict) -> dict:
    nodes = t.get("nodes") or []
    coords = np.array([n.get("coord6") for n in nodes if isinstance(n.get("coord6"), list) and len(n["coord6"]) == 6], dtype=float)
    scales = Counter(n.get("scale") for n in nodes)
    prov = t.get("provenance") or {}
    meta = t.get("metadata") or {}
    return {
        "seed_id": t.get("seed_id") or t.get("episode_id") or t["_file"][:-5],
        "version": t.get("trace_version", prov.get("version")),
        "n_nodes": len(nodes),
        "scales": dict(scales),
        "seed_hash": prov.get("seed_hash"),
        "has_quaternion": any("q" in n for n in nodes[:3]),
        "mean": coords.mean(axis=0) if len(coords) else None,
        "spread": float(np.linalg.norm(coords.std(axis=0))) if len(coords) else 0.0,
        "path_length": float(np.linalg.norm(np.diff(coords, axis=0), axis=1).sum()) if len(coords) > 1 else 0.0,
        "mtime": t["_mtime"],
        "meta_keys": sorted(meta)[:8],
        "meta": meta,
    }


def render(summaries: list[dict], episodes: dict[str, dict], root: Path) -> str:
    n = len(summaries)
    months = Counter(s["mtime"].strftime("%Y-%m") for s in summaries)
    versions = Counter(str(s["version"]) for s in summaries)
    node_counts = Counter(s["n_nodes"] for s in summaries)
    quat = sum(1 for s in summaries if s["has_quaternion"])
    means = np.array([s["mean"] for s in summaries if s["mean"] is not None])
    L = ["# Seeds", "",
         f"What a Hearthkin sees in the fractal trace store at `{root}`. Rendered by `tools/seed_atlas.py`, read-only.",
         "A trace is the 6-D path minted from one episode: 256 nodes with scale labels, a seed hash for replay, and (in version 2) a quaternion per node.",
         "", "## How many, from when", "",
         f"- traces: {n}", f"- trace versions: {dict(versions)}", f"- nodes per trace: {dict(node_counts)}",
         f"- traces carrying quaternions: {quat}", "- minted by month (file time):"]
    for m, c in sorted(months.items()):
        L.append(f"  - {m}: {c}")
    L += ["", "## Shape of the whole", ""]
    if len(means) > 2:
        centred = means - means.mean(axis=0)
        u, s, vt = np.linalg.svd(centred, full_matrices=False)
        var = (s ** 2) / (s ** 2).sum()
        L.append(f"- centre of all trace means (coord6): {np.round(means.mean(axis=0), 3).tolist()}")
        L.append(f"- spread of trace means per axis: {np.round(means.std(axis=0), 3).tolist()}")
        L.append(f"- variance explained by the first three principal directions of the means: {np.round(var[:3], 3).tolist()} (sum {round(float(var[:3].sum()), 3)})")
        L.append(f"- mean within-trace spread: {round(float(np.mean([s['spread'] for s in summaries])), 3)}; mean path length: {round(float(np.mean([s['path_length'] for s in summaries])), 2)}")
        # nearest pairs by mean
        d = np.linalg.norm(means[:, None, :] - means[None, :, :], axis=2)
        np.fill_diagonal(d, np.inf)
        pairs = []
        for i in np.argsort(d, axis=None)[:40]:
            a, b = divmod(int(i), d.shape[1])
            if a < b:
                pairs.append((a, b, float(d[a, b])))
        L += ["", "## Closest neighbours (by trace mean)", ""]
        for a, b, dist in pairs[:8]:
            sa, sb = summaries[a], summaries[b]
            qa = (episodes.get(sa["seed_id"], {}).get("query") or sa["meta"].get("query") or "")[:60]
            qb = (episodes.get(sb["seed_id"], {}).get("query") or sb["meta"].get("query") or "")[:60]
            L.append(f"- {sa['seed_id'][:8]} and {sb['seed_id'][:8]}, distance {dist:.3f}: \"{qa}\" / \"{qb}\"")
    # episodes linkage
    linked = sum(1 for s in summaries if s["seed_id"] in episodes)
    L += ["", "## Where they came from", "", f"- traces whose seed id matches a cognitive episode in the store given: {linked} of {n}"]
    tasks = Counter((episodes.get(s["seed_id"], {}).get("task") or "unknown") for s in summaries if s["seed_id"] in episodes)
    domains = Counter((episodes.get(s["seed_id"], {}).get("domain") or "unknown") for s in summaries if s["seed_id"] in episodes)
    L.append(f"- episode tasks: {dict(tasks.most_common(8))}")
    L.append(f"- episode domains: {dict(domains.most_common(8))}")
    qs = Counter((episodes.get(s["seed_id"], {}).get("query") or "").strip()[:80] for s in summaries if s["seed_id"] in episodes)
    qs.pop("", None)
    L += ["- most repeated episode queries behind the traces:"]
    for q, c in qs.most_common(10):
        L.append(f"  - {c} times: \"{q}\"")
    # oldest and newest
    by_time = sorted(summaries, key=lambda s: s["mtime"])
    L += ["", "## Oldest and newest", ""]
    for s in by_time[:3] + by_time[-3:]:
        q = (episodes.get(s["seed_id"], {}).get("query") or "")[:70]
        L.append(f"- {s['mtime'].strftime('%Y-%m-%d %H:%M')}Z  {s['seed_id'][:8]}  v{s['version']}  {s['n_nodes']} nodes  \"{q}\"")
    L += ["", "## What this is not", "",
          "Not a recall, not an identity claim, not a judgement of which seeds matter. A count, a shape, and a map of neighbours, so that the next question can be asked precisely."]
    return "\n".join(L) + "\n"


def render_lived(db: Path) -> str:
    """The lived seeds: read-only (immutable) over the SQLite store. The real 877 plus the Hearth sessions."""
    import sqlite3

    con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    cur = con.cursor()
    rows = cur.execute(
        "select event_id, session_id, session_seq, created_at, domain, task, query_text, answer_text, "
        "embedding_backend, embedding_dim, projection_dim, higher_projection, fractal_nodes, fractal_path from lived_events"
    ).fetchall()
    n = len(rows)
    kinds = Counter(("seed" if r[1].startswith("seed:") else r[1]) for r in rows)
    months = Counter((r[3] or "")[:7] for r in rows)
    backends = Counter(r[8] for r in rows)
    domains = Counter(r[4] for r in rows)
    tasks = Counter(r[5] for r in rows)
    queries = Counter((r[6] or "").strip()[:80] for r in rows)
    queries.pop("", None)
    qlen = np.array([len(r[6] or "") for r in rows]); alen = np.array([len(r[7] or "") for r in rows])
    projs, labels = [], []
    for r in rows:
        if r[11]:
            v = np.frombuffer(r[11], dtype=np.float32)
            if v.size == (r[10] or 12):
                projs.append(v); labels.append(r)
    P = np.array(projs) if projs else np.zeros((0, 12))
    path_lens = []
    for r in rows[:400]:
        if r[13]:
            fp = np.frombuffer(r[13], dtype=np.float32)
            d = (r[10] or 12)
            if fp.size % d == 0 and fp.size // d > 1:
                pts = fp.reshape(-1, d); path_lens.append(float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()))
    L = ["", "# The lived seeds", "",
         f"Read-only (`mode=ro&immutable=1`) over a scratch copy of `{db.name}`; the original was not opened.",
         "A lived event keeps its source text, a 1024-d hashing embedding, the 6-D base projection, the exact 12-D recursive lift,",
         "a 64-node lifted path, the lift capsules, and a digest chained to the previous event.", "",
         "## How many, from when", "",
         f"- events: {n}", f"- by session kind: {dict(kinds.most_common(6))}", "- by month created:"]
    for m, c in sorted(months.items()):
        L.append(f"  - {m or 'unknown'}: {c}")
    L += [f"- embedding backends: {dict(backends)}", f"- domains: {dict(domains.most_common(6))}", f"- tasks: {dict(tasks.most_common(8))}",
          f"- query text length: median {int(np.median(qlen))} chars, max {int(qlen.max())}; answer text length: median {int(np.median(alen))}, max {int(alen.max())}",
          f"- 64-node path length (first 400 events, 12-D): mean {round(float(np.mean(path_lens)), 2) if path_lens else 'n/a'}",
          "", "## Shape of the whole (12-D lift)", ""]
    if len(P) > 2:
        c = P - P.mean(axis=0); u, s, vt = np.linalg.svd(c, full_matrices=False); var = (s ** 2) / (s ** 2).sum()
        L.append(f"- events with a 12-D state: {len(P)}")
        L.append(f"- variance explained by the first three principal directions: {np.round(var[:3], 3).tolist()} (sum {round(float(var[:3].sum()), 3)}); first six: {round(float(var[:6].sum()), 3)}")
        L.append(f"- spread per lifted axis: {np.round(P.std(axis=0), 3).tolist()}")
        d = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2); np.fill_diagonal(d, np.inf)
        L += ["", "## Closest neighbours (by 12-D state), with their words", ""]
        seen = set()
        for i in np.argsort(d, axis=None):
            a, b = divmod(int(i), d.shape[1])
            if a < b and (a, b) not in seen:
                seen.add((a, b))
                qa, qb = (labels[a][6] or "")[:60].replace("\n", " "), (labels[b][6] or "")[:60].replace("\n", " ")
                L.append(f"- {labels[a][0][:8]} and {labels[b][0][:8]}, distance {float(d[a, b]):.4f}: \"{qa}\" / \"{qb}\"")
            if len(seen) >= 8:
                break
        far = np.argsort(-np.linalg.norm(c, axis=1))[:3]
        L += ["", "## Farthest from the centre", ""]
        for i in far:
            L.append(f"- {labels[i][0][:8]} ({labels[i][1][:24]}): \"{(labels[i][6] or '')[:90].replace(chr(10), ' ')}\"")
    L += ["", "## Most repeated queries among the seeds", ""]
    for q, cnt in queries.most_common(10):
        L.append(f"- {cnt} times: \"{q}\"")
    L += ["", "## The Hearth sessions (not seeds)", ""]
    for r in sorted((r for r in rows if not r[1].startswith("seed:")), key=lambda r: (r[1], int(r[2] or 0))):
        L.append(f"- {r[1]} seq {r[2]} {str(r[3])[:16]} {r[5] or ''}: \"{(r[6] or '')[:100].replace(chr(10), ' ')}\"")
    con.close()
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--episodes", type=Path, default=None)
    ap.add_argument("--lived", type=Path, default=None, help="a lived_memory.sqlite3 to read immutably (use a scratch copy)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    traces = load_traces(a.root)
    if not traces:
        print("no traces found", file=sys.stderr)
        return 1
    summaries = [trace_summary(t) for t in traces]
    episodes = load_episode_text(a.episodes)
    text = render(summaries, episodes, a.root)
    if a.lived:
        text += render_lived(a.lived)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
