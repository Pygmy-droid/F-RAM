#!/usr/bin/env python
"""Run calibration fit and optionally lint resulting payloads."""

import argparse
import subprocess
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_core.calibrate import main as calibrate_main



def _parse_wrapper_args(args: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--lint", action="store_true", help="Run calibration_lint on the produced payload.")
    parser.add_argument(
        "--lint-all",
        action="store_true",
        help="Run calibration_lint across all calibration*.json files in the output directory.",
    )
    parser.add_argument(
        "--lint-path",
        action="append",
        default=[],
        help="Additional calibration payload paths to validate after fitting.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Forward --strict to calibration_lint when linting.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print a calibration_status summary after fitting (text).",
    )
    parser.add_argument(
        "--status-json",
        action="store_true",
        help="Print calibration_status output in JSON after fitting.",
    )
    known, remaining = parser.parse_known_args(args)
    return known, remaining


def _parse_calibrate_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("storage/observability/calibration.jsonl"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("storage/index/demo_corpus/calibration.json"),
    )
    return parser.parse_args(argv)


def _run_lint(paths: list[Path], *, strict: bool) -> int:
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "calibration_lint.py")]
    if strict:
        cmd.append("--strict")
    cmd.extend(str(path) for path in paths)
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _run_status(storage_root: Path, corpus: str, *, as_json: bool) -> int:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "calibration_status.py"),
        "--storage-root",
        str(storage_root),
        "--corpus",
        corpus,
    ]
    if as_json:
        cmd.append("--json")
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _resolve_out_info(out_path: Path) -> tuple[Path, str]:
    resolved = out_path if out_path.is_absolute() else (Path.cwd() / out_path).resolve()
    corpus_dir = resolved.parent
    if corpus_dir.parent.name != "index":
        # best effort: treat parent as corpus and parent.parent as index root
        corpus = corpus_dir.name
        storage_root = corpus_dir.parent
        return storage_root, corpus
    corpus = corpus_dir.name
    storage_root = corpus_dir.parent.parent
    return storage_root, corpus


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    wrapper_args, remaining = _parse_wrapper_args(list(args))

    exit_code = calibrate_main(remaining)
    if exit_code != 0:
        return exit_code

    calibrate_opts = _parse_calibrate_args(remaining)
    out_path = Path(calibrate_opts.out)

    lint_requested = wrapper_args.lint or wrapper_args.lint_all or wrapper_args.lint_path
    if lint_requested:
        lint_targets = {out_path}
        lint_targets.update(Path(p) for p in wrapper_args.lint_path)
        if wrapper_args.lint_all:
            lint_targets.update(out_path.parent.glob("calibration*.json"))
        paths = sorted(path.resolve() for path in lint_targets if path.exists())
        if not paths:
            print("calibration_lint skipped: no payloads found to validate.")
        else:
            lint_exit = _run_lint(paths, strict=wrapper_args.strict)
            if lint_exit != 0:
                return lint_exit

    status_requested = wrapper_args.status or wrapper_args.status_json
    if status_requested:
        storage_root, corpus = _resolve_out_info(out_path)
        status_exit = _run_status(storage_root, corpus, as_json=wrapper_args.status_json)
        if status_exit != 0:
            return status_exit

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
