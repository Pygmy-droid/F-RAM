"""Validate the bounded F-RAM hot-context packet against Git reality."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

MAX_PACKET_BYTES = 8 * 1024
DEFAULT_PACKET = Path("docs/context/HOT_CONTEXT.md")

FIELD_PATTERNS = {
    "Packet": re.compile(r"^Packet:\s*`([^`]+)`\s*$", re.MULTILINE),
    "Canonical branch": re.compile(
        r"^Canonical branch:\s*`([^`]+)`\s*$", re.MULTILINE
    ),
    "Observed implementation head": re.compile(
        r"^Observed implementation head:\s*`?([0-9a-fA-F]{7,40})`?\s*$",
        re.MULTILINE,
    ),
    "Worktree": re.compile(r"^Worktree:\s*`([^`]+)`\s*$", re.MULTILINE),
}
PROTECTED_RE = re.compile(
    r"^Protected:\s*`([^`]+)`\s+on\s+`([^`]+)`\s+(?:—|-)\s+no writes\s*$",
    re.MULTILINE | re.IGNORECASE,
)
REQUIRED_SECTIONS = (
    "Mission",
    "Binding invariants",
    "Canonical state",
    "Active lanes",
    "Next gates",
    "Blind edges",
    "Expand only when needed",
)

# A commit after the packet commit is review-sensitive when it can change
# implementation identity, operating policy, an active proof/experiment, or the
# bounded bootstrap itself. Historical artifacts outside these rules may land
# without making an otherwise valid packet stale.
WATCHED_PATH_RULES = (
    "AGENTS.md",
    "AGENTS.override.md",
    "Makefile",
    "pyproject.toml",
    "requirements*.txt",
    ".github/**",
    "data/**",
    "devcontainer/**",
    "examples/**",
    "fram_core/**",
    "fram_eval/**",
    "fram_index/**",
    "fram_layout/**",
    "fram_serving/**",
    "experiments/**",
    "scripts/**",
    "skills/**",
    "tests/**",
    "tools/**",
    "docs/context/**",
    "docs/proof/**",
    "docs/Architecture.md",
    "docs/CODEX_DIARY.md",
    "docs/Context_Carryover.md",
    "docs/F-RAM-roadmap.md",
    "docs/README.md",
    "docs/WHAT_WORKS.md",
    "prompts/**",
)


@dataclass(frozen=True)
class PacketCheck:
    ok: bool
    review_required: bool
    observed_head: str | None
    current_head: str | None
    packet_commit: str | None
    canonical_branch: str | None
    canonical_worktree: str | None
    protected_worktree: str | None
    protected_branch: str | None
    commits_since_observation: int | None
    commits_since_packet: int | None
    watched_changes: tuple[str, ...]
    errors: tuple[str, ...]
    review_reasons: tuple[str, ...]

    @property
    def structurally_valid(self) -> bool:
        return not self.errors

    @property
    def status(self) -> str:
        if self.errors:
            return "FAIL"
        if self.review_required:
            return "REVIEW_REQUIRED"
        return "OK"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _single_line(result: subprocess.CompletedProcess[str]) -> str | None:
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _parse_single(
    text: str,
    label: str,
    pattern: re.Pattern[str],
    errors: list[str],
) -> str | None:
    matches = pattern.findall(text)
    if len(matches) != 1:
        errors.append(f"packet must contain exactly one '{label}' field")
        return None
    value = matches[0]
    if isinstance(value, tuple):
        raise TypeError("_parse_single only accepts single-group patterns")
    return value.strip()


def _validate_sections(text: str, errors: list[str]) -> None:
    for section in REQUIRED_SECTIONS:
        pattern = re.compile(
            rf"^## {re.escape(section)}(?:[ \t]+[^\r\n]*)?\r?$\r?\n"
            rf"(?P<body>.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            errors.append(f"packet must contain exactly one non-empty '## {section}' section")
        elif not matches[0].group("body").strip():
            errors.append(f"packet section '## {section}' must not be empty")


def _matches_watched_rule(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    for rule in WATCHED_PATH_RULES:
        if rule.endswith("/**"):
            if normalized.startswith(rule[:-2]):
                return True
        elif "*" in rule:
            prefix, suffix = rule.split("*", 1)
            if normalized.startswith(prefix) and normalized.endswith(suffix):
                return True
        elif normalized == rule:
            return True
    return False


def _empty_result(*errors: str) -> PacketCheck:
    return PacketCheck(
        ok=False,
        review_required=False,
        observed_head=None,
        current_head=None,
        packet_commit=None,
        canonical_branch=None,
        canonical_worktree=None,
        protected_worktree=None,
        protected_branch=None,
        commits_since_observation=None,
        commits_since_packet=None,
        watched_changes=(),
        errors=tuple(errors),
        review_reasons=(),
    )


def check_packet(
    repo: Path,
    packet: Path = DEFAULT_PACKET,
    *,
    max_bytes: int = MAX_PACKET_BYTES,
) -> PacketCheck:
    """Check packet schema, coordinates, Git order, and semantic freshness."""

    requested_repo = repo.resolve()
    repo_root_text = _single_line(_git(requested_repo, "rev-parse", "--show-toplevel"))
    if repo_root_text is None:
        return _empty_result(f"not a Git worktree: {requested_repo}")
    repo_root = Path(repo_root_text).resolve()

    packet_path = packet if packet.is_absolute() else repo_root / packet
    if not packet_path.is_file():
        return _empty_result(f"packet not found: {packet_path}")

    errors: list[str] = []
    review_reasons: list[str] = []
    payload = packet_path.read_bytes()
    if len(payload) > max_bytes:
        errors.append(f"packet is {len(payload)} bytes; limit is {max_bytes}")

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _empty_result(f"packet is not UTF-8: {exc}")

    _validate_sections(text, errors)
    _parse_single(text, "Packet", FIELD_PATTERNS["Packet"], errors)
    canonical_branch = _parse_single(
        text, "Canonical branch", FIELD_PATTERNS["Canonical branch"], errors
    )
    observed = _parse_single(
        text,
        "Observed implementation head",
        FIELD_PATTERNS["Observed implementation head"],
        errors,
    )
    if observed is not None:
        observed = observed.lower()
    worktree_text = _parse_single(text, "Worktree", FIELD_PATTERNS["Worktree"], errors)

    protected_matches = PROTECTED_RE.findall(text)
    if len(protected_matches) != 1:
        errors.append(
            "packet must contain exactly one 'Protected' field with path, branch, and 'no writes'"
        )
        protected_text = None
        protected_branch = None
    else:
        protected_text, protected_branch = (
            protected_matches[0][0].strip(),
            protected_matches[0][1].strip(),
        )

    try:
        relative_packet = packet_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        errors.append("packet must be inside the repository")
        relative_packet = None

    caller_packet_commit: str | None = None
    if relative_packet is not None:
        tracked = _git(repo_root, "ls-files", "--error-unmatch", "--", relative_packet)
        if tracked.returncode != 0:
            errors.append("packet is not tracked by Git")
        status = _git(
            repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            relative_packet,
        )
        if status.returncode != 0:
            errors.append("unable to inspect packet worktree status")
        elif status.stdout.strip():
            errors.append("packet has uncommitted changes")
        caller_packet_commit = _single_line(
            _git(repo_root, "log", "-1", "--format=%H", "--", relative_packet)
        )
        if caller_packet_commit is None:
            errors.append("packet has no committed Git provenance")

    canonical_path = Path(worktree_text).expanduser().resolve() if worktree_text else None
    canonical_root: Path | None = None
    current: str | None = None
    actual_canonical_branch: str | None = None
    packet_commit: str | None = None
    if canonical_path is not None:
        canonical_root_text = _single_line(
            _git(canonical_path, "rev-parse", "--show-toplevel")
        )
        if canonical_root_text is None:
            errors.append(f"declared canonical worktree is not a Git worktree: {canonical_path}")
        else:
            canonical_root = Path(canonical_root_text).resolve()
            if _normalized_path(canonical_root) != _normalized_path(canonical_path):
                errors.append(
                    "declared canonical worktree does not match its Git top-level"
                )
            actual_canonical_branch = _single_line(
                _git(canonical_root, "branch", "--show-current")
            )
            if canonical_branch and actual_canonical_branch != canonical_branch:
                errors.append(
                    "declared canonical branch does not match the canonical worktree "
                    f"({canonical_branch!r} != {actual_canonical_branch!r})"
                )
            current = _single_line(_git(canonical_root, "rev-parse", "HEAD"))
            if relative_packet is not None:
                packet_commit = _single_line(
                    _git(
                        canonical_root,
                        "log",
                        "-1",
                        "--format=%H",
                        "--",
                        relative_packet,
                    )
                )
                if packet_commit is None:
                    errors.append("packet has no commit in canonical history")
                elif (
                    caller_packet_commit is not None
                    and caller_packet_commit != packet_commit
                ):
                    errors.append(
                        "packet provenance differs between this worktree and canonical"
                    )

    protected_path = (
        Path(protected_text).expanduser().resolve() if protected_text else None
    )
    if protected_path is not None:
        protected_root_text = _single_line(
            _git(protected_path, "rev-parse", "--show-toplevel")
        )
        if protected_root_text is None:
            errors.append(f"declared protected path is not a Git worktree: {protected_path}")
        else:
            protected_root = Path(protected_root_text).resolve()
            if _normalized_path(protected_root) != _normalized_path(protected_path):
                errors.append("declared protected path does not match its Git top-level")
            actual_protected_branch = _single_line(
                _git(protected_root, "branch", "--show-current")
            )
            if protected_branch and actual_protected_branch != protected_branch:
                errors.append(
                    "declared protected branch does not match the protected worktree "
                    f"({protected_branch!r} != {actual_protected_branch!r})"
                )
            if canonical_path and _normalized_path(protected_root) == _normalized_path(
                canonical_path
            ):
                errors.append("canonical and protected worktrees must be distinct")

    commits_since_observation: int | None = None
    commits_since_packet: int | None = None
    watched_changes: tuple[str, ...] = ()
    if observed is not None and canonical_root is not None:
        resolved_observed = _single_line(
            _git(canonical_root, "rev-parse", "--verify", f"{observed}^{{commit}}")
        )
        if resolved_observed is None:
            errors.append(f"observed implementation head does not exist: {observed}")
        elif packet_commit is not None and current is not None:
            observed = resolved_observed
            observed_before_packet = _git(
                canonical_root, "merge-base", "--is-ancestor", observed, packet_commit
            )
            if observed == packet_commit or observed_before_packet.returncode != 0:
                errors.append(
                    "observed implementation head must strictly precede the packet commit"
                )

            packet_before_current = _git(
                canonical_root,
                "merge-base",
                "--is-ancestor",
                packet_commit,
                current,
            )
            if packet_before_current.returncode != 0:
                errors.append("packet commit is not an ancestor of current canonical HEAD")

            observed_before_current = _git(
                canonical_root, "merge-base", "--is-ancestor", observed, current
            )
            if observed_before_current.returncode != 0:
                errors.append(
                    "observed implementation head is not an ancestor of current canonical HEAD"
                )
            else:
                count = _single_line(
                    _git(canonical_root, "rev-list", "--count", f"{observed}..{current}")
                )
                commits_since_observation = int(count) if count is not None else None
                if commits_since_observation is None:
                    errors.append("unable to count commits since the observation")

            if packet_before_current.returncode == 0:
                count = _single_line(
                    _git(
                        canonical_root,
                        "rev-list",
                        "--count",
                        f"{packet_commit}..{current}",
                    )
                )
                commits_since_packet = int(count) if count is not None else None
                if commits_since_packet is None:
                    errors.append("unable to count commits since the packet")
                elif commits_since_packet:
                    changed_result = _git(
                        canonical_root,
                        "diff",
                        "--name-only",
                        f"{packet_commit}..{current}",
                    )
                    if changed_result.returncode != 0:
                        errors.append("unable to inspect paths changed since the packet")
                    else:
                        changed = tuple(
                            line.strip()
                            for line in changed_result.stdout.splitlines()
                            if line.strip()
                        )
                        watched_changes = tuple(
                            path for path in changed if _matches_watched_rule(path)
                        )
                        if watched_changes:
                            review_reasons.append(
                                "watched paths changed after the packet commit: "
                                + ", ".join(watched_changes)
                            )
    elif current is None:
        errors.append("unable to resolve current canonical HEAD")

    review_required = not errors and bool(review_reasons)
    return PacketCheck(
        ok=not errors and not review_required,
        review_required=review_required,
        observed_head=observed,
        current_head=current,
        packet_commit=packet_commit,
        canonical_branch=canonical_branch,
        canonical_worktree=str(canonical_path) if canonical_path else None,
        protected_worktree=str(protected_path) if protected_path else None,
        protected_branch=protected_branch,
        commits_since_observation=commits_since_observation,
        commits_since_packet=commits_since_packet,
        watched_changes=watched_changes,
        errors=tuple(errors),
        review_reasons=tuple(review_reasons),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate docs/context/HOT_CONTEXT.md against canonical Git state."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    args = parser.parse_args(argv)

    result = check_packet(args.repo, args.packet)
    if result.errors:
        for error in result.errors:
            print(f"[context] FAIL: {error}")
        return 1
    if result.review_required:
        for reason in result.review_reasons:
            print(f"[context] REVIEW_REQUIRED: {reason}")
        print(
            "[context] REVIEW_REQUIRED: "
            f"observed={result.observed_head} "
            f"current={result.current_head} "
            f"packet_commit={result.packet_commit} "
            f"commits_since_packet={result.commits_since_packet}"
        )
        return 2

    print(
        "[context] OK: "
        f"observed={result.observed_head} "
        f"current={result.current_head} "
        f"packet_commit={result.packet_commit} "
        f"commits_since_observation={result.commits_since_observation} "
        f"commits_since_packet={result.commits_since_packet}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
