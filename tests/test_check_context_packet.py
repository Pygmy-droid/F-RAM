from __future__ import annotations

import subprocess
from pathlib import Path

from tools.check_context_packet import MAX_PACKET_BYTES, check_packet, main


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path, branch: str) -> str:
    path.mkdir()
    _git(path, "init", "-b", branch)
    _git(path, "config", "user.name", "Context Test")
    _git(path, "config", "user.email", "context@example.invalid")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "base")
    return _git(path, "rev-parse", "HEAD")


def _make_repos(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    protected = tmp_path / "protected"
    observed = _init_repo(repo, "canonical")
    _init_repo(protected, "protected")
    return repo, protected, observed


def _packet_text(
    *,
    observed: str,
    repo: Path,
    protected: Path,
    canonical_branch: str = "canonical",
    protected_branch: str = "protected",
) -> str:
    return f"""# F-RAM Hot Context

Packet: `HC-TEST`
Canonical branch: `{canonical_branch}`
Observed implementation head: `{observed}`
Worktree: `{repo}`
Protected: `{protected}` on `{protected_branch}` — no writes

## Mission

Preserve bounded context.

## Binding invariants

- Code and tests at reviewed current HEAD define implementation reality.

## Canonical state `[INTEGRATION-GRADE]`

- The test repository is canonical.

## Active lanes

- One test writer owns the packet.

## Next gates

1. Validate the packet.

## Blind edges

- None beyond the test scope.

## Expand only when needed

- Read the relevant test.
"""


def _commit_packet(
    repo: Path,
    protected: Path,
    observed: str,
    **overrides: str,
) -> str:
    packet = repo / "docs" / "context" / "HOT_CONTEXT.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(
        _packet_text(
            observed=observed,
            repo=Path(overrides.pop("worktree", repo)),
            protected=Path(overrides.pop("protected", protected)),
            **overrides,
        ),
        encoding="utf-8",
    )
    _git(repo, "add", packet.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "add hot packet")
    return _git(repo, "rev-parse", "HEAD")


def test_packet_accepts_a_bounded_current_packet(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    packet_commit = _commit_packet(repo, protected, observed)

    result = check_packet(repo)

    assert result.ok
    assert result.status == "OK"
    assert result.observed_head == observed
    assert result.packet_commit == packet_commit
    assert result.current_head == packet_commit
    assert result.commits_since_observation == 1
    assert result.commits_since_packet == 0


def test_packet_rejects_missing_required_field_and_section(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    text = _packet_text(observed=observed, repo=repo, protected=protected)
    text = text.replace(f"Protected: `{protected}` on `protected` — no writes\n", "")
    text = text.replace("## Blind edges\n\n- None beyond the test scope.\n\n", "")
    packet = repo / "docs" / "context" / "HOT_CONTEXT.md"
    packet.parent.mkdir(parents=True)
    packet.write_text(text, encoding="utf-8")
    _git(repo, "add", packet.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "add malformed packet")

    result = check_packet(repo)

    assert not result.ok
    assert any("'Protected'" in error for error in result.errors)
    assert any("'## Blind edges'" in error for error in result.errors)


def test_packet_rejects_duplicate_observed_field(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    text = _packet_text(observed=observed, repo=repo, protected=protected)
    text = text.replace(
        f"Observed implementation head: `{observed}`\n",
        f"Observed implementation head: `{observed}`\n"
        f"Observed implementation head: `{observed}`\n",
    )
    packet = repo / "docs" / "context" / "HOT_CONTEXT.md"
    packet.parent.mkdir(parents=True)
    packet.write_text(text, encoding="utf-8")
    _git(repo, "add", packet.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "add duplicate field")

    result = check_packet(repo)

    assert not result.ok
    assert any("exactly one 'Observed implementation head'" in e for e in result.errors)


def test_packet_rejects_nonexistent_observation(tmp_path: Path) -> None:
    repo, protected, _ = _make_repos(tmp_path)
    _commit_packet(repo, protected, "f" * 40)

    result = check_packet(repo)

    assert not result.ok
    assert any("does not exist" in error for error in result.errors)


def test_packet_rejects_nonancestor_observation(tmp_path: Path) -> None:
    repo, protected, base = _make_repos(tmp_path)
    _git(repo, "checkout", "-b", "other")
    (repo / "other.txt").write_text("other\n", encoding="utf-8")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-m", "other history")
    observed = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "canonical")
    assert _git(repo, "rev-parse", "HEAD") == base
    _commit_packet(repo, protected, observed)

    result = check_packet(repo)

    assert not result.ok
    assert any("strictly precede" in error for error in result.errors)
    assert any("not an ancestor of current" in error for error in result.errors)


def test_packet_rejects_observation_that_did_not_precede_packet(
    tmp_path: Path,
) -> None:
    repo, protected, base = _make_repos(tmp_path)
    _git(repo, "checkout", "-b", "future")
    (repo / "future.txt").write_text("future\n", encoding="utf-8")
    _git(repo, "add", "future.txt")
    _git(repo, "commit", "-m", "future observation")
    observed = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "canonical")
    assert _git(repo, "rev-parse", "HEAD") == base
    _commit_packet(repo, protected, observed)
    _git(repo, "merge", "--no-ff", "future", "-m", "merge future")

    result = check_packet(repo)

    assert not result.ok
    assert any("strictly precede" in error for error in result.errors)
    assert not any("not an ancestor of current" in error for error in result.errors)


def test_packet_rejects_outside_repository(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    outside = tmp_path / "HOT_CONTEXT.md"
    outside.write_text(
        _packet_text(observed=observed, repo=repo, protected=protected),
        encoding="utf-8",
    )

    result = check_packet(repo, outside)

    assert not result.ok
    assert any("inside the repository" in error for error in result.errors)


def test_packet_rejects_uncommitted_changes(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(repo, protected, observed)
    packet = repo / "docs" / "context" / "HOT_CONTEXT.md"
    packet.write_text(packet.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = check_packet(repo)

    assert not result.ok
    assert any("uncommitted changes" in error for error in result.errors)


def test_packet_rejects_wrong_canonical_branch(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(
        repo,
        protected,
        observed,
        canonical_branch="not-the-current-branch",
    )

    result = check_packet(repo)

    assert not result.ok
    assert any("canonical branch does not match" in error for error in result.errors)


def test_packet_rejects_wrong_canonical_worktree(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(repo, protected, observed, worktree=str(protected))

    result = check_packet(repo)

    assert not result.ok
    assert any("canonical branch does not match" in error for error in result.errors)
    assert any("canonical and protected worktrees must be distinct" in e for e in result.errors)


def test_packet_rejects_wrong_protected_branch(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(
        repo,
        protected,
        observed,
        protected_branch="not-the-protected-branch",
    )

    result = check_packet(repo)

    assert not result.ok
    assert any("protected branch does not match" in error for error in result.errors)


def test_packet_requires_review_after_watched_change(
    tmp_path: Path, capsys
) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(repo, protected, observed)
    changed = repo / "fram_core" / "new_behavior.py"
    changed.parent.mkdir()
    changed.write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", changed.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "change watched behavior")

    result = check_packet(repo)

    assert result.structurally_valid
    assert result.review_required
    assert not result.ok
    assert result.status == "REVIEW_REQUIRED"
    assert result.watched_changes == ("fram_core/new_behavior.py",)
    assert main(["--repo", str(repo)]) == 2
    assert "REVIEW_REQUIRED" in capsys.readouterr().out


def test_packet_allows_unwatched_provenance_commit(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    _commit_packet(repo, protected, observed)
    note = repo / "notes" / "historical-observation.md"
    note.parent.mkdir()
    note.write_text("cold provenance only\n", encoding="utf-8")
    _git(repo, "add", note.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "add unwatched provenance")

    result = check_packet(repo)

    assert result.ok
    assert not result.review_required
    assert result.commits_since_packet == 1
    assert result.watched_changes == ()


def test_packet_rejects_oversize_payload(tmp_path: Path) -> None:
    repo, protected, observed = _make_repos(tmp_path)
    packet = repo / "docs" / "context" / "HOT_CONTEXT.md"
    packet.parent.mkdir(parents=True)
    packet.write_text(
        _packet_text(observed=observed, repo=repo, protected=protected)
        + ("x" * MAX_PACKET_BYTES),
        encoding="utf-8",
    )
    _git(repo, "add", packet.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "add oversize packet")

    result = check_packet(repo)

    assert not result.ok
    assert any("limit is" in error for error in result.errors)
