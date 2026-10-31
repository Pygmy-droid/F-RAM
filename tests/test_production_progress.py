"""Windows reader locks cannot silently discard or de-atomize gate progress."""

from pathlib import Path

import pytest

from fram_eval import production_memory_eval as evaluation


def sharing_error(code=32):
    error = PermissionError("synthetic sharing lock")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_transient_windows_lock_retries_same_atomic_replace(
    tmp_path, monkeypatch, code
):
    source = tmp_path / "receipt.tmp"
    target = tmp_path / "receipt.json"
    source.write_text("new complete receipt")
    target.write_text("old complete receipt")
    original = Path.replace
    attempts, sleeps = [], []

    def replace(path, destination):
        attempts.append((path, destination))
        if len(attempts) < 3:
            assert target.read_text() == "old complete receipt"
            assert source.read_text() == "new complete receipt"
            raise sharing_error(code)
        return original(path, destination)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(evaluation.time, "sleep", sleeps.append)
    evaluation._replace_progress(source, target)
    assert attempts == [(source, target)] * 3
    assert sleeps == [0.01, 0.02]
    assert target.read_text() == "new complete receipt"
    assert not source.exists()


@pytest.mark.parametrize("windows_lock", [True, False])
def test_persistent_or_other_permission_error_fails_visibly(
    tmp_path, monkeypatch, windows_lock
):
    source = tmp_path / "receipt.tmp"
    target = tmp_path / "receipt.json"
    source.write_text("new")
    target.write_text("old")
    attempts, sleeps = [], []
    error = sharing_error() if windows_lock else PermissionError("real denial")

    def replace(path, destination):
        attempts.append((path, destination))
        raise error

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(evaluation.time, "sleep", sleeps.append)
    with pytest.raises(PermissionError) as caught:
        evaluation._replace_progress(source, target)
    assert caught.value is error
    assert len(attempts) == (8 if windows_lock else 1)
    assert sum(sleeps) <= 1.28
    assert target.read_text() == "old"
    assert source.read_text() == "new"
