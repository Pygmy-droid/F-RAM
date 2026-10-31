from __future__ import annotations

from typing import Dict, List


def list_sources() -> List[Dict[str, str]]:
    """Return available connector sources (stubbed)."""
    return [
        {"id": "fake_1", "name": "Fake Connector 1"},
        {"id": "fake_2", "name": "Fake Connector 2"},
    ]


def fetch_items(source_id: str, max_items: int) -> List[Dict[str, str]]:
    """Return deterministic fake items for the given source."""
    max_items = max(0, int(max_items))
    items: List[Dict[str, str]] = []
    for i in range(max_items):
        item_id = f"{source_id}_item_{i}"
        items.append(
            {
                "source_id": source_id,
                "id": item_id,
                "version_id": item_id,
                "text": f"item {i} from {source_id}",
            }
        )
    return items
