from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer


def test_cognitive_memory_embedding_scoring(tmp_path: Path) -> None:
    store = CognitiveMemoryStore(tmp_path)
    store.append_episode(
        query="Alpha project status",
        domain="general",
        task="qa",
        answer="Alpha launch remains on track for Q4.",
        citations=["alpha.md:chunk0"],
        trace_id="alpha-trace",
    )
    store.append_episode(
        query="Beta budget update",
        domain="general",
        task="qa",
        answer="Beta burn increased 20 percent month-over-month.",
        citations=["beta.md:chunk0"],
        trace_id="beta-trace",
    )

    cfg = FRAMConfig.from_env()
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)

    results = store.search("alpha project update", k=1, vectorizer=vectorizer)
    assert results, "expected at least one memory hit"
    top = results[0]
    assert top["kind"] == "episode"
    assert float(top["_score"]) > 0.0
    assert top.get("trace_id") == "alpha-trace"


def test_bootstrap_memory_cli_files(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    cognitive_dir = storage_root / "memory" / "cognitive"
    cognitive_dir.mkdir(parents=True, exist_ok=True)
    episode_path = cognitive_dir / "episodes.jsonl"
    payload = {
        "id": "bridge-1",
        "type": "episode",
        "time": "2025-10-10T10:00:00Z",
        "query": "What happened yesterday?",
        "answer": "We closed the always-on memory milestone.",
        "domain": "general",
        "task": "qa",
    }
    episode_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    cmd = [
        sys.executable,
        "tools/bootstrap_memory.py",
        "--source",
        "files",
        "--storage-root",
        str(storage_root),
        "--window",
        "1",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Counts:" in result.stdout
    assert "Recent episodes" in result.stdout


def test_cognitive_memory_summary_cli(tmp_path: Path) -> None:
    log_path = tmp_path / "memory_cognitive.jsonl"
    events = [
        {
            "backend": "hashing",
            "selected": [{"tokens": 42}, {"tokens": 18}],
            "selected_count": 2,
            "token_budget": 300,
        },
        {
            "backend": "hashing",
            "selected": [{"tokens": 10}],
            "selected_count": 1,
            "token_budget": 150,
        },
    ]
    with log_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")

    cmd = [
        sys.executable,
        "tools/cognitive_memory_summary.py",
        "--path",
        str(log_path),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Total events: 2" in result.stdout
    assert "hashing" in result.stdout


def test_session_warmup_cli(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    cognitive_dir = storage_root / "memory" / "cognitive"
    cognitive_dir.mkdir(parents=True, exist_ok=True)
    store = CognitiveMemoryStore(cognitive_dir)
    store.append_episode(
        query="Always-on memory status",
        domain="general",
        task="qa",
        answer="Session warmup confirms cognitive hydration.",
        citations=["note.md:chunk0"],
        trace_id="warmup-trace",
    )

    script = Path(__file__).resolve().parents[1] / "tools" / "session_warmup.py"
    cmd = [
        sys.executable,
        str(script),
        "--no-docs",
        "--memory-query",
        "Always-on memory status",
        "--memory-source",
        "files",
        "--storage-root",
        str(storage_root),
        "--json",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["memory"]["results"], "expected cognitive memory results"


def test_session_warmup_identity(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    script = Path(__file__).resolve().parents[1] / "tools" / "session_warmup.py"
    cmd = [
        sys.executable,
        str(script),
        "--no-docs",
        "--memory-source",
        "files",
        "--storage-root",
        str(storage_root),
        "--identity-name",
        "Arion",
        "--identity-note",
        "Celebration identity",
        "--no-memory",
        "--json",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        check=True,
    )
    meta_path = storage_root / "memory" / "cognitive" / "beliefs.meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    segment_name = meta.get("active_segment")
    segment_path = meta_path.parent / segment_name
    assert segment_path.exists()
    contents = segment_path.read_text(encoding="utf-8")
    assert "Arion" in contents
    assert "Celebration identity" in contents
