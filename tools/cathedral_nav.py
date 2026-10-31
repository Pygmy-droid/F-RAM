#!/usr/bin/env python3
"""Navigate the Cosmic Cathedral from the terminal.

The first step under Rick's roadmap page (Cathedral, then browser and
computer use): a way for a model to move through the map without a human
clicking for it. Reads the same JSON the viewer polls, so it sees exactly what
Rick sees, minus the colour.

Usage (from the repository root):
    python tools/cathedral_nav.py now                   # cards in progress, next up, counts
    python tools/cathedral_nav.py find lived memory     # best matching nodes for a cue
    python tools/cathedral_nav.py show pl-lived         # one node, its fields, its neighbours
    python tools/cathedral_nav.py near wb-0004 --depth 2  # what is within two hops
    python tools/cathedral_nav.py path hearth m:fram_core/pipeline.py   # shortest route
    python tools/cathedral_nav.py whatis fram_serving/app.py            # the node for a file
    python tools/cathedral_nav.py pipeline pl-fractal   # files and tests of a pipeline
    python tools/cathedral_nav.py strata                # strata with node counts
    python tools/cathedral_nav.py theory                # the theory lineage, oldest first
    python tools/cathedral_nav.py --json ...            # any command as JSON

Standard library only. Read-only: it never writes the map or the Workbook.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP = REPO_ROOT / "experiments" / "cosmic_cathedral" / "cosmic-cathedral-map.json"


class Cathedral:
    def __init__(self, path: Path = MAP):
        self.map_path = path  # not `self.path`: that name is the route-finding method below
        data = json.loads(path.read_text(encoding="utf-8"))
        self.data = data
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]
        self.out: dict[str, list[dict]] = {}
        self.inc: dict[str, list[dict]] = {}
        for e in self.edges:
            self.out.setdefault(e["source"], []).append(e)
            self.inc.setdefault(e["target"], []).append(e)
        self.by_path = {n["path"]: n["id"] for n in data["nodes"] if n.get("path")}
        self.strata = {s["id"]: s for s in data.get("strata", [])}

    # -- lookups

    def resolve(self, ref: str) -> str | None:
        """Accept a node id, a card id, a file path, or a label fragment."""
        if ref in self.nodes:
            return ref
        low = ref.lower()
        if low in self.nodes:
            return low
        if ref in self.by_path:
            return self.by_path[ref]
        norm = ref.replace("\\", "/")
        if norm in self.by_path:
            return self.by_path[norm]
        if "m:" + norm in self.nodes:
            return "m:" + norm
        hits = self.find(ref, limit=1)
        return hits[0][1]["id"] if hits and hits[0][0] >= 5 else None

    def find(self, query: str, limit: int = 8) -> list[tuple[int, dict]]:
        whole = query.lower().strip()
        terms = [t for t in re.split(r"\s+", whole) if t]
        scored = []
        for n in self.nodes.values():
            label = n["label"].lower()
            hay = " ".join(str(n.get(k, "") or "") for k in ("label", "path", "summary", "kind", "authority",
                                                             "claim_state", "stratum", "work_state", "card", "pipeline")).lower()
            score = 0
            if label == whole or n["id"].lower() == whole:
                score += 20  # an exact name beats any pile of partial matches
            for t in terms:
                if len(t) <= 3 and t not in (n["id"].lower(), label):
                    continue  # "the", "of", "py": too short to mean anything on their own
                if label == t:
                    score += 10
                elif t in label:
                    score += 5
                if (n.get("path") or "").lower().find(t) >= 0:
                    score += 3
                if n["id"].lower().find(t) >= 0:
                    score += 3
                if t in hay:
                    score += 1
            if score:
                scored.append((score, n))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return scored[:limit]

    def neighbours(self, nid: str) -> list[tuple[str, str, dict]]:
        res = []
        for e in self.out.get(nid, []):
            res.append(("->", e["relation"], self.nodes[e["target"]]))
        for e in self.inc.get(nid, []):
            res.append(("<-", e["relation"], self.nodes[e["source"]]))
        return res

    def within(self, nid: str, depth: int) -> dict[str, int]:
        seen = {nid: 0}
        q = deque([nid])
        while q:
            cur = q.popleft()
            if seen[cur] >= depth:
                continue
            for _, _, n in self.neighbours(cur):
                if n["id"] not in seen:
                    seen[n["id"]] = seen[cur] + 1
                    q.append(n["id"])
        return seen

    def path(self, a: str, b: str) -> list[tuple[str, str]] | None:
        """Shortest undirected path, returned as (relation, node_id) steps."""
        prev: dict[str, tuple[str, str] | None] = {a: None}
        q = deque([a])
        while q:
            cur = q.popleft()
            if cur == b:
                break
            for direction, rel, n in self.neighbours(cur):
                if n["id"] not in prev:
                    prev[n["id"]] = (cur, f"{rel}" if direction == "->" else f"is {rel} by")
                    q.append(n["id"])
        if b not in prev:
            return None
        steps = []
        cur = b
        while prev[cur] is not None:
            p, rel = prev[cur]
            steps.append((rel, cur))
            cur = p
        steps.reverse()
        return steps

    # -- views

    def now(self) -> dict:
        cards = [n for n in self.nodes.values() if n.get("work_state")]
        cards.sort(key=lambda n: n["priority"])
        return {
            "head": self.data.get("head", "")[:7],
            "branch": self.data.get("branch"),
            "generated_utc": self.data.get("generated_utc"),
            "summary": self.data.get("summary"),
            "in_progress": [c for c in cards if c["work_state"] == "in_progress"],
            "next": [c for c in cards if c["work_state"] == "not_started"][:5],
            "finished": [c for c in cards if c["work_state"] == "finished"][-5:],
        }

    def pipeline(self, pid: str) -> dict | None:
        p = self.nodes.get(pid)
        if not p or p.get("kind") != "pipeline":
            return None
        files = [self.nodes[e["target"]] for e in self.out.get(pid, []) if e["relation"] == "contains"]
        cards = [self.nodes[e["source"]] for e in self.inc.get(pid, []) if self.nodes[e["source"]].get("work_state")]
        return {"pipeline": p, "modules": [f for f in files if f["kind"] == "module"],
                "tests": [f for f in files if f["kind"] == "test"], "cards": cards}


# -- formatting


def short(n: dict) -> str:
    bits = [n["id"], n["label"]]
    if n.get("work_state"):
        bits.append(f"[{n['work_state']} rank {n['priority']}]")
    elif n.get("kind") in ("module", "test"):
        bits.append(f"[{n.get('pipeline')}, {n.get('commits')} commits, {n.get('first_commit')} to {n.get('last_commit')}]")
    else:
        bits.append(f"[{n['kind']} · {n.get('claim_state')} · {n['stratum']}]")
    return "  ".join(bits)


def print_node(c: Cathedral, n: dict) -> None:
    print(f"{n['label']}  ({n['id']})")
    print(f"  kind {n['kind']} · claim {n.get('claim_state')} · stratum {n['stratum']} · scope {n.get('scope')} · worktree {n.get('worktree_state')}")
    if n.get("path"):
        print(f"  path {n['path']}" + (f"  ({n.get('bytes')} bytes, sha256 {str(n.get('sha256'))[:12]})" if n.get("bytes") else ""))
    for k in ("pipeline", "work_state", "priority", "loc", "commits", "first_commit", "last_commit", "era", "files", "tests", "started", "finished"):
        if n.get(k) not in (None, "", [], {}):
            print(f"  {k} {n[k]}")
    print(f"  {n['summary']}")
    nb = c.neighbours(n["id"])
    if nb:
        print(f"  connections ({len(nb)}):")
        for direction, rel, m in sorted(nb, key=lambda x: (x[0], x[1], x[2]["id"]))[:40]:
            print(f"    {direction} {rel:18} {m['id']}  {m['label']}")
        if len(nb) > 40:
            print(f"    ... and {len(nb) - 40} more")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Navigate the Cosmic Cathedral from the terminal.")
    ap.add_argument("--map", type=Path, default=MAP)
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("now")
    p = sub.add_parser("find"); p.add_argument("query", nargs="+"); p.add_argument("--limit", type=int, default=8)
    p = sub.add_parser("show"); p.add_argument("ref")
    p = sub.add_parser("near"); p.add_argument("ref"); p.add_argument("--depth", type=int, default=1)
    p = sub.add_parser("path"); p.add_argument("a"); p.add_argument("b")
    p = sub.add_parser("whatis"); p.add_argument("file")
    p = sub.add_parser("pipeline"); p.add_argument("pid")
    sub.add_parser("strata")
    sub.add_parser("theory")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    c = Cathedral(a.map)

    def emit(obj):
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))

    if a.cmd == "now":
        r = c.now()
        if a.json:
            emit(r); return 0
        s = r["summary"]
        print(f"Cathedral at {r['head']} on {r['branch']} · {s['nodes']} nodes · {s['edges']} edges · generated {r['generated_utc']}")
        print(f"cards {s['cards']}")
        print("in progress:")
        for n in r["in_progress"] or []:
            print("  " + short(n))
        if not r["in_progress"]:
            print("  nothing")
        print("next:")
        for n in r["next"]:
            print("  " + short(n))
        print("recently finished:")
        for n in r["finished"]:
            print("  " + short(n))
        return 0
    if a.cmd == "find":
        hits = c.find(" ".join(a.query), a.limit)
        if a.json:
            emit([{"score": s, **n} for s, n in hits]); return 0
        for s, n in hits:
            print(f"{s:3}  {short(n)}")
        if not hits:
            print("nothing recognised; nothing invented")
        return 0
    if a.cmd in ("show", "near", "whatis"):
        ref = a.file if a.cmd == "whatis" else a.ref
        nid = c.resolve(ref)
        if not nid:
            print(f"no node for {ref!r}", file=sys.stderr); return 1
        if a.cmd == "near":
            seen = c.within(nid, a.depth)
            rows = sorted(((d, c.nodes[i]) for i, d in seen.items()), key=lambda x: (x[0], x[1]["id"]))
            if a.json:
                emit([{"hops": d, **n} for d, n in rows]); return 0
            for d, n in rows:
                print(f"{d}  {short(n)}")
            return 0
        if a.json:
            emit({**c.nodes[nid], "connections": [{"direction": d, "relation": r, "id": m["id"], "label": m["label"]} for d, r, m in c.neighbours(nid)]}); return 0
        print_node(c, c.nodes[nid]); return 0
    if a.cmd == "path":
        x, y = c.resolve(a.a), c.resolve(a.b)
        if not x or not y:
            print(f"could not resolve {'a' if not x else 'b'}", file=sys.stderr); return 1
        steps = c.path(x, y)
        if steps is None:
            print(f"no route between {x} and {y}"); return 1
        if a.json:
            emit({"from": x, "to": y, "steps": [{"relation": r, "id": i, "label": c.nodes[i]["label"]} for r, i in steps]}); return 0
        print(f"{x}  {c.nodes[x]['label']}")
        for r, i in steps:
            print(f"  --{r}--> {i}  {c.nodes[i]['label']}")
        print(f"{len(steps)} hop(s)")
        return 0
    if a.cmd == "pipeline":
        r = c.pipeline(a.pid)
        if not r:
            print(f"no pipeline {a.pid!r}; try: {', '.join(i for i, n in c.nodes.items() if n.get('kind') == 'pipeline')}", file=sys.stderr); return 1
        if a.json:
            emit(r); return 0
        p = r["pipeline"]
        print(f"{p['label']}  ({p['id']}) · {p['files']} files · {p['tests']} tests · {p['loc']} lines · {p['commits']} commits · {p['first_commit']} to {p['last_commit']} · {p['era']}")
        print(f"  {p['summary']}")
        for n in r["cards"]:
            print(f"  card {short(n)}")
        print("  modules:")
        for m in sorted(r["modules"], key=lambda m: m["path"]):
            print(f"    {m['path']:60} {m.get('loc', 0):5} lines  {m.get('commits', 0):3} commits  {m.get('worktree_state')}")
        print("  tests:")
        for m in sorted(r["tests"], key=lambda m: m["path"]):
            print(f"    {m['path']}")
        return 0
    if a.cmd == "strata":
        counts: dict[str, int] = {}
        for n in c.nodes.values():
            counts[n["stratum"]] = counts.get(n["stratum"], 0) + 1
        rows = [(s["id"], s["label"], s["z"], counts.get(s["id"], 0)) for s in c.data.get("strata", [])]
        if a.json:
            emit(rows); return 0
        for sid, label, z, cnt in sorted(rows, key=lambda r: -r[2]):
            print(f"{z:6}  {cnt:4}  {sid:14} {label}")
        return 0
    if a.cmd == "theory":
        th = [n for n in c.nodes.values() if n["stratum"] == "theory"]
        if a.json:
            emit(th); return 0
        for n in sorted(th, key=lambda n: n["id"]):
            print(short(n))
            print(f"      {n['summary'][:160]}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
