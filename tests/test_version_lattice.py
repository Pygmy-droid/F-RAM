from datetime import datetime, timezone, timedelta

from fram_index.version_lattice import VersionLattice, VersionNode, append_version_record


def test_version_lattice_active_ids_filters_future_nodes():
    lattice = VersionLattice()
    now = datetime.now(timezone.utc)
    lattice.add_node(VersionNode(node_id="v1", timestamp=now - timedelta(days=2)))
    lattice.add_node(VersionNode(node_id="v2", timestamp=now + timedelta(days=2)))

    active = lattice.active_ids(now)
    assert "v1" in active and "v2" not in active


def test_version_lattice_active_version_map_prefers_latest():
    lattice = VersionLattice()
    t1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2025, 2, 1, tzinfo=timezone.utc)
    lattice.add_node(VersionNode(node_id="doc@v1", timestamp=t1))
    lattice.add_node(VersionNode(node_id="doc@v2", timestamp=t2))

    mapping = lattice.active_version_map(t2)
    assert mapping["doc"] == "doc@v2"

    mapping_early = lattice.active_version_map(t1)
    assert mapping_early["doc"] == "doc@v1"


def test_version_lattice_select_ids_explicit():
    lattice = VersionLattice()
    now = datetime.now(timezone.utc)
    lattice.add_node(VersionNode(node_id="doc@v1", timestamp=now))
    lattice.add_node(VersionNode(node_id="doc@v2", timestamp=now))

    ids = lattice.select_ids(as_of=now, version_id="doc@v1")
    assert ids == {"doc@v1"}

    missing = lattice.select_ids(as_of=now, version_id="missing")
    assert missing == set()


def test_version_manifest_roundtrip(tmp_path):
    manifest = tmp_path / "versions.jsonl"
    t0 = datetime.now(timezone.utc)
    n1 = VersionNode(node_id="v1", timestamp=t0, diff={"added": 1})
    n2 = VersionNode(node_id="v2", timestamp=t0 + timedelta(seconds=10), parents=("v1",), diff={"delta": "v1->v2"})

    append_version_record(manifest, n1)
    append_version_record(manifest, n2)

    lattice = VersionLattice.from_manifest(manifest)

    assert len(lattice) == 2
    assert lattice.ancestors("v2") == {"v1"}
    active = lattice.active_ids(t0 + timedelta(seconds=20))
    assert active == {"v1", "v2"}
