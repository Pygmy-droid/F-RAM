from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_SCAN_DIRS = ("docs", "prompts")
DEFAULT_EXTENSIONS = (
    ".md",
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".jsonl",
    ".txt",
    ".ini",
    ".cfg",
    ".ps1",
    ".sh",
    ".cmd",
)


@dataclass(frozen=True, slots=True)
class NulFinding:
    path: Path
    nul_count: int


def _iter_files(paths: Sequence[Path], *, extensions: Sequence[str]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                if extensions and child.suffix.lower() not in extensions:
                    continue
                yield child
        elif path.is_file():
            if extensions and path.suffix.lower() not in extensions:
                continue
            yield path


def find_nul_bytes(paths: Sequence[Path], *, extensions: Sequence[str] = DEFAULT_EXTENSIONS) -> list[NulFinding]:
    findings: list[NulFinding] = []
    for file_path in _iter_files(paths, extensions=extensions):
        try:
            data = file_path.read_bytes()
        except OSError:
            continue
        count = data.count(b"\x00")
        if count:
            findings.append(NulFinding(path=file_path, nul_count=count))
    return findings


def strip_nul_bytes(path: Path) -> int:
    data = path.read_bytes()
    count = data.count(b"\x00")
    if not count:
        return 0
    cleaned = data.replace(b"\x00", b"")
    path.write_bytes(cleaned)
    return count


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail (or optionally fix) if any scanned text file contains NUL bytes.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=list(DEFAULT_SCAN_DIRS),
        help="Files/directories to scan (default: docs prompts).",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Strip NUL bytes in-place for any offending files.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    roots = [Path(p) for p in (args.paths or [])]
    findings = find_nul_bytes(roots)
    if not findings:
        return 0

    if args.fix:
        fixed = 0
        for finding in findings:
            try:
                fixed += strip_nul_bytes(finding.path)
            except OSError:
                continue
        findings = find_nul_bytes(roots)
        if not findings:
            print(f"Stripped {fixed} NUL bytes.")
            return 0

    print("NUL bytes detected:")
    for finding in findings:
        print(f"- {finding.path} ({finding.nul_count} bytes)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

