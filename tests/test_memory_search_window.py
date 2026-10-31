from __future__ import annotations

from pathlib import Path

from fram_serving import observability


def test_memory_search_window_written(tmp_path):
    obs_root = tmp_path / "observability"
    entry = {
        "query_preview": "memory search check",
        "backend": "hashing",
        "results": 2,
        "selected_total": 2,
        "selected_used": 1,
        "selected_dropped": 1,
        "token_budget": 0,
        "slot_budget": 3,
        "ann_enabled": True,
        "ann_returned": 1,
        "ann_backend": "hashing",
    }
    snapshot = observability.update_memory_search_window(obs_root, entry, maxlen=3)
    assert snapshot is not None
    path = obs_root / "memory_search.json"
    assert path.exists()
    payload = path.read_text(encoding="utf-8")
    assert "memory-search-1" in payload
