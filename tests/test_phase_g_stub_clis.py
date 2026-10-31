from __future__ import annotations

from tools import phase_g_archive, phase_g_compact, phase_g_snapshot


def test_phase_g_compact_stub_runs():
    assert phase_g_compact.main(["--dry-run"]) == 0


def test_phase_g_archive_stub_runs():
    assert phase_g_archive.main(["--dry-run"]) == 0


def test_phase_g_snapshot_stub_runs():
    assert phase_g_snapshot.main([]) == 0
