from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fram_index.version_lattice import VersionLattice, VersionNode


def test_version_lattice_active_ids_timezone_aware():
    lattice = VersionLattice()
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc)
    lattice.add_node(VersionNode(node_id="a", timestamp=t0))
    lattice.add_node(VersionNode(node_id="b", timestamp=t1))

    # Naive datetime treated as UTC by implementation
    naive = datetime(2025, 1, 2, 0, 0)
    ids = lattice.active_ids(naive)
    assert "a" in ids
    # Before t1 noon, node b might not be included
    assert ("b" in ids) == (naive.replace(tzinfo=timezone.utc) >= t1)

    # Explicit aware time just after t1 includes both
    aware = t1 + timedelta(seconds=1)
    ids2 = lattice.active_ids(aware)
    assert ids2 == {"a", "b"}

