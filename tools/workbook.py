#!/usr/bin/env python3
"""The Workbook: cards, a priority order, three states, and an event chain.

Rick's rooting structure, rebuilt 2026-10-29 from the designs in his Sticky
Notes (Feb to Apr 2026) and the continuity ledger pattern. This is a
reconstruction, not the original.

    workbook/EVENTS.jsonl   source of truth: append-only, hash-chained events
    workbook/WORKBOOK.md    rendered: every card, grouped by state, in priority order
    workbook/STATUS.md      rendered: where we are right now
    workbook/IDEAS.md       the idea lane, written by hand

States:  not_started -> in_progress -> finished  (reopen goes back to in_progress)
Priority: a single ordered list. Rank 1 is the most important. Moving a card
          shifts the others, so ranks are always unique and gap-free.

Usage (copy-paste ready, from the repository root):

    python tools/workbook.py add "Title of the work" --desc "What and why"
    python tools/workbook.py start WB-0001
    python tools/workbook.py finish WB-0001
    python tools/workbook.py reopen WB-0001
    python tools/workbook.py note WB-0001 "Something learned"
    python tools/workbook.py priority WB-0003 1
    python tools/workbook.py link WB-0001 --files tools/workbook.py --nodes hearth
    python tools/workbook.py list
    python tools/workbook.py show WB-0001
    python tools/workbook.py autolog        # attach commits that mention a card id
    python tools/workbook.py render         # rewrite WORKBOOK.md and STATUS.md
    python tools/workbook.py check --strict # chain, states, rendered files current
    python tools/workbook.py sync           # autolog + render + check

Standard library only. No network. Writes only inside workbook/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_DIR = "workbook"
EVENTS_NAME = "EVENTS.jsonl"
WORKBOOK_NAME = "WORKBOOK.md"
STATUS_NAME = "STATUS.md"
IDEAS_NAME = "IDEAS.md"

STATES = ("not_started", "in_progress", "finished")
STATE_LABELS = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "finished": "Finished",
}
EVENT_TYPES = frozenset(
    {"card_added", "state_changed", "priority_changed", "note", "linked", "commit"}
)
CARD_ID = re.compile(r"\bWB-\d{4}\b")
GENESIS = "GENESIS"


# ----------------------------------------------------------------- helpers


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_actor(root: Path) -> str:
    env = os.environ.get("WORKBOOK_ACTOR")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "config", "user.name"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        )
        if out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ----------------------------------------------------------------- model


@dataclass
class Card:
    id: str
    title: str
    description: str = ""
    state: str = "not_started"
    files: list[str] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    started: str | None = None
    finished: str | None = None
    notes: list[dict] = field(default_factory=list)
    commits: list[dict] = field(default_factory=list)
    actor: str = ""

    def to_dict(self, rank: int) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state,
            "priority": rank,
            "files": list(self.files),
            "nodes": list(self.nodes),
            "created": self.created,
            "updated": self.updated,
            "started": self.started,
            "finished": self.finished,
            "notes": list(self.notes),
            "commits": list(self.commits),
            "actor": self.actor,
        }


@dataclass
class State:
    cards: dict[str, Card] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)  # priority order, rank 1 first
    head_hash: str = GENESIS
    last_ts: str = ""
    event_count: int = 0
    logged_commits: set[tuple[str, str]] = field(default_factory=set)

    def rank(self, card_id: str) -> int:
        return self.order.index(card_id) + 1

    def ordered(self, state: str | None = None) -> list[Card]:
        cards = [self.cards[c] for c in self.order]
        return [c for c in cards if state is None or c.state == state]

    def as_dict(self) -> dict:
        return {
            "head_hash": self.head_hash,
            "last_ts": self.last_ts,
            "event_count": self.event_count,
            "cards": [self.cards[c].to_dict(i + 1) for i, c in enumerate(self.order)],
        }


def reduce_events(events: list[dict]) -> State:
    """Pure reducer: the same events always give the same state."""
    s = State()
    for e in events:
        t = e["type"]
        cid = e.get("card")
        d = e.get("data", {})
        ts = e["ts"]
        if t == "card_added":
            card = Card(
                id=cid, title=d["title"], description=d.get("description", ""),
                files=list(d.get("files", [])), nodes=list(d.get("nodes", [])),
                created=ts, updated=ts, actor=e.get("actor", ""),
            )
            s.cards[cid] = card
            pos = d.get("priority")
            if pos is None or pos > len(s.order):
                s.order.append(cid)
            else:
                s.order.insert(max(0, pos - 1), cid)
        elif t == "state_changed":
            card = s.cards[cid]
            card.state = d["to"]
            card.updated = ts
            if d["to"] == "in_progress" and card.started is None:
                card.started = ts
            if d["to"] == "finished":
                card.finished = ts
            if d["to"] != "finished":
                card.finished = None
        elif t == "priority_changed":
            s.order.remove(cid)
            pos = min(max(1, d["to"]), len(s.order) + 1)
            s.order.insert(pos - 1, cid)
            s.cards[cid].updated = ts
        elif t == "note":
            s.cards[cid].notes.append({"ts": ts, "actor": e.get("actor", ""), "text": d["text"]})
            s.cards[cid].updated = ts
        elif t == "linked":
            card = s.cards[cid]
            for f in d.get("files", []):
                if f not in card.files:
                    card.files.append(f)
            for n in d.get("nodes", []):
                if n not in card.nodes:
                    card.nodes.append(n)
            card.updated = ts
        elif t == "commit":
            s.cards[cid].commits.append(
                {"sha": d["sha"], "short": d["sha"][:7], "subject": d["subject"], "committed": d["committed"]}
            )
            s.logged_commits.add((d["sha"], cid))
            s.cards[cid].updated = ts
        s.head_hash = e["hash"]
        s.last_ts = ts
        s.event_count = e["seq"]
    return s


# ----------------------------------------------------------------- workbook


class WorkbookError(Exception):
    pass


class Workbook:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or REPO_ROOT)
        self.dir = self.root / WORKBOOK_DIR
        self.events_path = self.dir / EVENTS_NAME
        self.workbook_path = self.dir / WORKBOOK_NAME
        self.status_path = self.dir / STATUS_NAME
        self.ideas_path = self.dir / IDEAS_NAME

    # -- events

    def load_events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        with open(self.events_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def verify_chain(self, events: list[dict]) -> list[str]:
        errors: list[str] = []
        prev, prev_seq, prev_ts = GENESIS, 0, ""
        for e in events:
            seq = e.get("seq")
            body = {k: v for k, v in e.items() if k != "hash"}
            if sha256_text(canonical(body)) != e.get("hash"):
                errors.append(f"seq {seq}: hash does not match content")
            if e.get("prev_hash") != prev:
                errors.append(f"seq {seq}: chain broken, prev_hash does not match seq {prev_seq}")
            if seq != prev_seq + 1:
                errors.append(f"seq {seq}: expected seq {prev_seq + 1}")
            if e.get("ts", "") < prev_ts:
                errors.append(f"seq {seq}: timestamp goes backwards")
            if e.get("type") not in EVENT_TYPES:
                errors.append(f"seq {seq}: unknown event type {e.get('type')!r}")
            prev, prev_seq, prev_ts = e.get("hash", ""), seq or prev_seq, e.get("ts", prev_ts)
        return errors

    def state(self) -> State:
        events = self.load_events()
        errors = self.verify_chain(events)
        if errors:
            raise WorkbookError("event chain is broken:\n  " + "\n  ".join(errors))
        return reduce_events(events)

    def _append(self, events: list[dict], etype: str, card: str | None, data: dict, actor: str) -> dict:
        prev = events[-1]["hash"] if events else GENESIS
        seq = events[-1]["seq"] + 1 if events else 1
        ts = now_utc()
        if events and ts < events[-1]["ts"]:
            ts = events[-1]["ts"]
        entry = {
            "seq": seq, "ts": ts, "type": etype, "card": card,
            "actor": actor, "data": data, "prev_hash": prev,
        }
        entry["hash"] = sha256_text(canonical(entry))
        events.append(entry)
        return entry

    def _write_events(self, events: list[dict]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.events_path.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for e in events:
                f.write(canonical(e) + "\n")
        os.replace(tmp, self.events_path)

    def _commit(self, etype: str, card: str | None, data: dict, actor: str) -> dict:
        events = self.load_events()
        errors = self.verify_chain(events)
        if errors:
            raise WorkbookError("refusing to append to a broken chain:\n  " + "\n  ".join(errors))
        entry = self._append(events, etype, card, data, actor)
        self._write_events(events)
        return entry

    # -- commands

    def add(self, title: str, description: str = "", files: list[str] | None = None,
            nodes: list[str] | None = None, priority: int | None = None, actor: str = "") -> str:
        title = title.strip()
        if not title:
            raise WorkbookError("a card needs a title")
        st = self.state()
        cid = f"WB-{len(st.cards) + 1:04d}"
        while cid in st.cards:
            cid = f"WB-{int(cid[3:]) + 1:04d}"
        data = {"title": title, "description": description.strip(),
                "files": sorted(set(files or [])), "nodes": sorted(set(nodes or []))}
        if priority is not None:
            data["priority"] = int(priority)
        self._commit("card_added", cid, data, actor)
        return cid

    def _require(self, st: State, cid: str) -> Card:
        cid = cid.upper()
        if cid not in st.cards:
            raise WorkbookError(f"no such card: {cid}")
        return st.cards[cid]

    def set_state(self, cid: str, to: str, actor: str = "") -> None:
        st = self.state()
        card = self._require(st, cid)
        if to not in STATES:
            raise WorkbookError(f"unknown state {to!r}; use one of {', '.join(STATES)}")
        if card.state == to:
            raise WorkbookError(f"{card.id} is already {STATE_LABELS[to].lower()}")
        allowed = {
            ("not_started", "in_progress"), ("not_started", "finished"),
            ("in_progress", "finished"), ("in_progress", "not_started"),
            ("finished", "in_progress"),
        }
        if (card.state, to) not in allowed:
            raise WorkbookError(f"{card.id}: cannot go from {card.state} to {to}")
        self._commit("state_changed", card.id, {"from": card.state, "to": to}, actor)

    def note(self, cid: str, text: str, actor: str = "") -> None:
        st = self.state()
        card = self._require(st, cid)
        if not text.strip():
            raise WorkbookError("an empty note is not a note")
        self._commit("note", card.id, {"text": text.strip()}, actor)

    def priority(self, cid: str, rank: int, actor: str = "") -> None:
        st = self.state()
        card = self._require(st, cid)
        rank = int(rank)
        if rank < 1:
            raise WorkbookError("rank 1 is the top; there is nothing above it")
        if st.rank(card.id) == rank:
            raise WorkbookError(f"{card.id} is already rank {rank}")
        self._commit("priority_changed", card.id, {"from": st.rank(card.id), "to": rank}, actor)

    def link(self, cid: str, files: list[str] | None = None, nodes: list[str] | None = None, actor: str = "") -> None:
        st = self.state()
        card = self._require(st, cid)
        files = sorted(set(files or []) - set(card.files))
        nodes = sorted(set(nodes or []) - set(card.nodes))
        if not files and not nodes:
            raise WorkbookError("nothing new to link")
        self._commit("linked", card.id, {"files": files, "nodes": nodes}, actor)

    def autolog(self, actor: str = "autolog") -> list[tuple[str, str]]:
        """Attach every commit whose message mentions a card id. Idempotent."""
        st = self.state()
        if not st.cards:
            return []
        try:
            out = subprocess.run(
                ["git", "-C", str(self.root), "log", "--all", "--reverse",
                 "--format=%H%x1f%ct%x1f%s%x1f%b%x1e"],
                capture_output=True, text=True, check=True, encoding="utf-8", errors="replace",
            ).stdout
        except subprocess.CalledProcessError:
            return []
        added: list[tuple[str, str]] = []
        events = self.load_events()
        for rec in out.split("\x1e"):
            rec = rec.strip("\n")
            if not rec.strip():
                continue
            parts = rec.split("\x1f")
            if len(parts) < 3:
                continue
            sha, ct, subject = parts[0].strip(), parts[1], parts[2]
            body = parts[3] if len(parts) > 3 else ""
            for cid in sorted(set(CARD_ID.findall(subject + "\n" + body))):
                if cid not in st.cards or (sha, cid) in st.logged_commits:
                    continue
                committed = datetime.fromtimestamp(int(ct), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                self._append(events, "commit", cid, {"sha": sha, "subject": subject.strip(), "committed": committed}, actor)
                st.logged_commits.add((sha, cid))
                added.append((sha[:7], cid))
        if added:
            self._write_events(events)
        return added

    # -- rendering

    def render_workbook(self, st: State) -> str:
        lines = [
            "# Workbook",
            "",
            f"Rendered from `{WORKBOOK_DIR}/{EVENTS_NAME}` by `tools/workbook.py`. Do not edit by hand;",
            "change a card with the tool and the next render replaces this file.",
            "",
            f"Events: {st.event_count} · chain head `{st.head_hash[:12]}` · last event {st.last_ts or 'none'}",
            "",
            "Rank 1 is the most important. States: not started, in progress, finished.",
            "",
        ]
        for state in ("in_progress", "not_started", "finished"):
            cards = st.ordered(state)
            lines.append(f"## {STATE_LABELS[state]} ({len(cards)})")
            lines.append("")
            if not cards:
                lines.append("_none_")
                lines.append("")
                continue
            for c in cards:
                lines.append(f"### {c.id} · rank {st.rank(c.id)} · {c.title}")
                lines.append("")
                if c.description:
                    lines.append(c.description)
                    lines.append("")
                meta = [f"created {c.created[:10]}"]
                if c.started:
                    meta.append(f"started {c.started[:10]}")
                if c.finished:
                    meta.append(f"finished {c.finished[:10]}")
                meta.append(f"updated {c.updated[:10]}")
                lines.append("- " + " · ".join(meta))
                if c.files:
                    lines.append("- files: " + ", ".join(f"`{f}`" for f in c.files))
                if c.nodes:
                    lines.append("- cathedral nodes: " + ", ".join(f"`{n}`" for n in c.nodes))
                if c.commits:
                    lines.append("- commits:")
                    for k in c.commits[-8:]:
                        lines.append(f"  - `{k['short']}` {k['subject']} ({k['committed'][:10]})")
                if c.notes:
                    lines.append("- notes:")
                    for n in c.notes:
                        who = f" ({n['actor']})" if n.get("actor") else ""
                        lines.append(f"  - {n['ts'][:10]}{who}: {n['text']}")
                lines.append("")
        return "\n".join(lines).rstrip("\n") + "\n"

    def render_status(self, st: State) -> str:
        doing = st.ordered("in_progress")
        todo = st.ordered("not_started")
        done = sorted(st.ordered("finished"), key=lambda c: c.finished or "", reverse=True)
        lines = [
            "# Status",
            "",
            f"Rendered from `{WORKBOOK_DIR}/{EVENTS_NAME}` by `tools/workbook.py`. Where we are, in one page.",
            "",
            f"Cards: {len(st.cards)} · in progress {len(doing)} · not started {len(todo)} · finished {len(done)}",
            f"Last event: {st.last_ts or 'none'} · chain head `{st.head_hash[:12]}` · events {st.event_count}",
            "",
            "## Now",
            "",
        ]
        if doing:
            for c in doing:
                lines.append(f"- **{c.id}** rank {st.rank(c.id)}: {c.title}")
                if c.notes:
                    lines.append(f"  - last note: {c.notes[-1]['text']}")
                if c.commits:
                    lines.append(f"  - last commit: `{c.commits[-1]['short']}` {c.commits[-1]['subject']}")
        else:
            lines.append("_nothing in progress_")
        lines += ["", "## Next", ""]
        if todo:
            for c in todo[:5]:
                lines.append(f"- **{c.id}** rank {st.rank(c.id)}: {c.title}")
            if len(todo) > 5:
                lines.append(f"- and {len(todo) - 5} more, see WORKBOOK.md")
        else:
            lines.append("_nothing queued_")
        lines += ["", "## Recently finished", ""]
        if done:
            for c in done[:5]:
                lines.append(f"- **{c.id}** {c.title} ({(c.finished or '')[:10]})")
        else:
            lines.append("_nothing finished yet_")
        lines += [
            "",
            "## Rhythm",
            "",
            "One seam. One proof. One stamp. Then safe. (Rick and Hearthkin, 2026-04-11)",
            "",
            "Context protocol: build to 65 percent, controlled burn to 70, then the idea lane",
            f"in `{WORKBOOK_DIR}/{IDEAS_NAME}` until compression. (Rick, 2026-03-04)",
        ]
        return "\n".join(lines).rstrip("\n") + "\n"

    def render(self) -> State:
        st = self.state()
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.workbook_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.render_workbook(st))
        with open(self.status_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.render_status(st))
        if not self.ideas_path.exists():
            with open(self.ideas_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(IDEAS_TEMPLATE)
        return st

    # -- checking

    def check(self, strict: bool = False) -> dict:
        errors: list[str] = []
        warnings: list[str] = []
        events = self.load_events()
        if not events:
            errors.append("no events: the workbook is empty")
            return {"ok": False, "errors": errors, "warnings": warnings, "events": 0, "cards": 0}
        errors += self.verify_chain(events)
        st = reduce_events(events) if not errors else State()
        if not errors:
            if len(st.order) != len(st.cards) or set(st.order) != set(st.cards):
                errors.append("priority order and card set disagree")
            for c in st.cards.values():
                if c.state not in STATES:
                    errors.append(f"{c.id}: unknown state {c.state!r}")
                if c.state == "in_progress" and not c.started:
                    errors.append(f"{c.id}: in progress without a start time")
                if c.state == "finished" and not c.finished:
                    errors.append(f"{c.id}: finished without a finish time")
                for f_ in c.files:
                    if not (self.root / f_).exists():
                        warnings.append(f"{c.id}: linked file missing: {f_}")
            if len(st.ordered("in_progress")) > 2:
                warnings.append("more than two cards in progress; the rhythm says one seam, two at most")
            for path, render_fn in ((self.workbook_path, self.render_workbook), (self.status_path, self.render_status)):
                if not path.exists():
                    (errors if strict else warnings).append(f"{path.name} has not been rendered")
                elif path.read_text(encoding="utf-8").replace("\r\n", "\n") != render_fn(st):
                    (errors if strict else warnings).append(f"{path.name} is stale; run render")
        return {
            "ok": not errors, "errors": errors, "warnings": warnings,
            "events": len(events), "cards": len(st.cards),
            "head_hash": st.head_hash if not errors else None,
        }


IDEAS_TEMPLATE = """# Ideas

The idea lane. Above 70 percent of context, stop building and write here.
Format from Rick's note of 2026-03-04. Append only; newest at the bottom.

```
IDEA-YYYYMMDD-XX
Source:      observation / X / alpha test / architecture thought / Rick / Wren
Signal:      what changed or what was noticed
Hypothesis:  what it might mean
Relevance:   why it matters to F-RAM
Next action: explore / ignore / prototype later / card WB-xxxx
```

---
"""


# ----------------------------------------------------------------- cli


def _print_card(st: State, c: Card) -> None:
    print(f"{c.id}  rank {st.rank(c.id)}  {STATE_LABELS[c.state]:12}  {c.title}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The Workbook: cards, priority, three states.")
    ap.add_argument("--root", default=None, help="repository root (default: this repository)")
    ap.add_argument("--actor", default=None, help="who is acting (default: WORKBOOK_ACTOR or git user.name)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="add a card")
    p.add_argument("title")
    p.add_argument("--desc", default="")
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--nodes", nargs="*", default=[])
    p.add_argument("--priority", type=int, default=None)
    for name, help_ in (("start", "not started -> in progress"), ("finish", "-> finished"),
                        ("reopen", "finished -> in progress"), ("unstart", "in progress -> not started")):
        q = sub.add_parser(name, help=help_)
        q.add_argument("card")
    p = sub.add_parser("note", help="add a note to a card")
    p.add_argument("card")
    p.add_argument("text")
    p = sub.add_parser("priority", help="move a card to a rank (1 = top)")
    p.add_argument("card")
    p.add_argument("rank", type=int)
    p = sub.add_parser("link", help="attach files or cathedral nodes to a card")
    p.add_argument("card")
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--nodes", nargs="*", default=[])
    sub.add_parser("list", help="list cards in priority order")
    p = sub.add_parser("show", help="show one card")
    p.add_argument("card")
    sub.add_parser("autolog", help="attach commits that mention a card id")
    sub.add_parser("render", help="rewrite WORKBOOK.md and STATUS.md")
    p = sub.add_parser("check", help="verify the chain, the states, and the rendered files")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    sub.add_parser("sync", help="autolog, render, check")
    sub.add_parser("status", help="print STATUS.md")

    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    wb = Workbook(Path(a.root) if a.root else None)
    actor = a.actor or default_actor(wb.root)
    try:
        if a.cmd == "add":
            cid = wb.add(a.title, a.desc, a.files, a.nodes, a.priority, actor)
            wb.render()
            print(f"added {cid}: {a.title}")
        elif a.cmd in ("start", "finish", "reopen", "unstart"):
            to = {"start": "in_progress", "finish": "finished", "reopen": "in_progress", "unstart": "not_started"}[a.cmd]
            wb.set_state(a.card, to, actor)
            st = wb.render()
            _print_card(st, st.cards[a.card.upper()])
        elif a.cmd == "note":
            wb.note(a.card, a.text, actor)
            wb.render()
            print(f"noted on {a.card.upper()}")
        elif a.cmd == "priority":
            wb.priority(a.card, a.rank, actor)
            st = wb.render()
            for c in st.ordered():
                _print_card(st, c)
        elif a.cmd == "link":
            wb.link(a.card, a.files, a.nodes, actor)
            wb.render()
            print(f"linked on {a.card.upper()}")
        elif a.cmd == "list":
            st = wb.state()
            for c in st.ordered():
                _print_card(st, c)
            if not st.cards:
                print("no cards yet")
        elif a.cmd == "show":
            st = wb.state()
            c = wb._require(st, a.card)
            print(json.dumps(c.to_dict(st.rank(c.id)), indent=2, ensure_ascii=False))
        elif a.cmd == "autolog":
            added = wb.autolog()
            wb.render()
            for sha, cid in added:
                print(f"logged {sha} -> {cid}")
            print(f"{len(added)} commit(s) attached")
        elif a.cmd == "render":
            st = wb.render()
            print(f"rendered {WORKBOOK_NAME} and {STATUS_NAME}: {len(st.cards)} cards, {st.event_count} events")
        elif a.cmd == "check":
            r = wb.check(strict=a.strict)
            if a.json:
                print(json.dumps(r, indent=2))
            else:
                for w in r["warnings"]:
                    print(f"WARN  {w}")
                for e in r["errors"]:
                    print(f"FAIL  {e}")
                if r["ok"]:
                    print(f"OK  {r['events']} events, {r['cards']} cards, chain intact")
            return 0 if r["ok"] else 1
        elif a.cmd == "sync":
            added = wb.autolog()
            wb.render()
            r = wb.check(strict=True)
            print(f"autolog: {len(added)} commit(s) attached")
            for w in r["warnings"]:
                print(f"WARN  {w}")
            for e in r["errors"]:
                print(f"FAIL  {e}")
            print(("OK  " if r["ok"] else "FAIL  ") + f"{r['events']} events, {r['cards']} cards")
            return 0 if r["ok"] else 1
        elif a.cmd == "status":
            print(wb.render_status(wb.state()), end="")
    except WorkbookError as exc:
        print(f"workbook: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
