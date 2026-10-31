from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig  # noqa: E402

_NO_DIFF = object()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit FRAM defaults or env-resolved config as JSON.")
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Load config via FRAMConfig.from_env() instead of raw defaults.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Include only fields that differ from defaults.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output path (prints to stdout if omitted).",
    )
    return parser.parse_args()


def _normalize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _config_dict(config: FRAMConfig) -> dict[str, Any]:
    if hasattr(config, "model_dump"):
        data = config.model_dump()
    else:
        data = config.dict()  # type: ignore[attr-defined]
    return _normalize(data)


def _diff_values(base: Any, current: Any) -> Any:
    if isinstance(base, dict) and isinstance(current, dict):
        output: dict[str, Any] = {}
        for key, value in current.items():
            if key not in base:
                output[key] = value
                continue
            diff = _diff_values(base[key], value)
            if diff is not _NO_DIFF:
                output[key] = diff
        return output if output else _NO_DIFF
    if base == current:
        return _NO_DIFF
    return current


def main() -> int:
    args = parse_args()
    source = "env" if args.from_env else "defaults"
    config = FRAMConfig.from_env() if args.from_env else FRAMConfig()
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "config": _config_dict(config),
    }
    if args.diff:
        base = _config_dict(FRAMConfig())
        diff = _diff_values(base, payload["config"])
        payload["diff"] = {} if diff is _NO_DIFF else diff
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out is None:
        sys.stdout.write(encoded + "\n")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
