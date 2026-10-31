"""Validate FRAM calibration payloads for logistic/conformal consistency."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig

REQUIRED_COEFFICIENTS = ("a", "b", "c", "g", "h", "d")
STRICT_MAX_TAU = 1.0
STRICT_MIN_GAP = 5e-3
STRICT_MAX_TEMPERATURE = 10.0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate calibration payload JSON files for FRAM confidence thresholds.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Calibration payload files to validate (defaults to storage/index/demo_corpus/calibration*.json).",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root when discovering default calibration files.",
    )
    parser.add_argument(
        "--corpus",
        default="demo_corpus",
        help="Index corpus folder to scan when no explicit paths are provided (default: demo_corpus).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable stricter bounds (0 < tau <= 1, min gap, temperature <= 10, no unknown coefficients).",
    )
    return parser.parse_args(argv)


def _discover_default_files(cfg: FRAMConfig, storage_root: Path, corpus: str) -> list[Path]:
    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index")
    corpus_dir = index_dir / corpus
    if not corpus_dir.exists():
        return []
    return sorted(corpus_dir.glob("calibration*.json"))


def _load_payload(path: Path) -> Mapping[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Calibration payload not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Calibration payload {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, Mapping):
        raise SystemExit(f"Calibration payload {path} must be a JSON object.")
    return data


def _as_float(payload: Mapping[str, Any], key: str, *, errors: list[str]) -> float | None:
    value = payload.get(key)
    if value is None:
        errors.append(f"missing {key}")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{key} is not numeric: {value!r}")
        return None
    return number


def _validate_coefficients(payload: Mapping[str, Any], errors: list[str], *, strict: bool) -> dict[str, float]:
    raw = payload.get("logistic_coefs")
    if raw is None:
        errors.append("missing logistic_coefs")
        return {}
    if not isinstance(raw, Mapping):
        errors.append("logistic_coefs must be an object")
        return {}
    coefs: dict[str, float] = {}
    for key in REQUIRED_COEFFICIENTS:
        if key not in raw:
            errors.append(f"logistic coefficient '{key}' missing")
            continue
        value = raw.get(key)
        try:
            coefs[key] = float(value)
        except (TypeError, ValueError):
            errors.append(f"logistic coefficient '{key}' is not numeric: {value!r}")
    for extra_key, extra_value in raw.items():
        if extra_key in REQUIRED_COEFFICIENTS:
            continue
        if strict:
            errors.append(f"unexpected logistic coefficient '{extra_key}' in strict mode")
            continue
        try:
            coefs[str(extra_key)] = float(extra_value)
        except (TypeError, ValueError):
            errors.append(f"logistic coefficient '{extra_key}' is not numeric: {extra_value!r}")
    return coefs


def _validate_payload(payload: Mapping[str, Any], *, strict: bool) -> tuple[list[str], dict[str, float]]:
    errors: list[str] = []
    tau1 = _as_float(payload, "tau1", errors=errors)
    tau2 = _as_float(payload, "tau2", errors=errors)
    temperature = _as_float(payload, "temperature", errors=errors)
    coefs = _validate_coefficients(payload, errors, strict=strict)

    if tau1 is not None:
        if tau1 <= 0:
            errors.append("tau1 must be positive")
        if strict and tau1 > STRICT_MAX_TAU:
            errors.append(f"tau1 must be <= {STRICT_MAX_TAU:.1f} in strict mode")
    if tau2 is not None:
        if tau2 < 0:
            errors.append("tau2 must be non-negative")
        if strict and tau2 > STRICT_MAX_TAU:
            errors.append(f"tau2 must be <= {STRICT_MAX_TAU:.1f} in strict mode")
    if tau1 is not None and tau2 is not None:
        gap = tau1 - tau2
        if tau2 >= tau1:
            errors.append("tau2 must be strictly less than tau1")
        elif strict and gap < STRICT_MIN_GAP:
            errors.append(f"tau1 - tau2 gap {gap:.4f} below strict minimum {STRICT_MIN_GAP:.4f}")
    if temperature is not None:
        if temperature <= 0:
            errors.append("temperature must be positive")
        if strict and temperature > STRICT_MAX_TEMPERATURE:
            errors.append(
                f"temperature {temperature:.3f} exceeds strict ceiling {STRICT_MAX_TEMPERATURE:.1f}"
            )
    if coefs.get("g", 0.0) < 0.0:
        errors.append(
            "logistic coefficient 'g' must be non-negative so centroid distance "
            "cannot increase confidence"
        )

    return errors, {"tau1": tau1, "tau2": tau2, "temperature": temperature, "coefs": coefs}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = FRAMConfig.from_env()
    storage_root = args.storage_root or cfg.STORAGE_ROOT

    if args.paths:
        paths = [path if path.is_absolute() else Path(path) for path in args.paths]
    else:
        paths = _discover_default_files(cfg, storage_root, args.corpus)
        if not paths:
            print("No calibration payloads found.")
            return 1

    had_error = False
    for path in paths:
        payload = _load_payload(path)
        errors, summary = _validate_payload(payload, strict=args.strict)
        if errors:
            had_error = True
            print(f"[FAIL] {path} -> {', '.join(errors)}")
            continue
        tau1 = summary["tau1"] or 0.0
        tau2 = summary["tau2"] or 0.0
        temperature = summary["temperature"] or 0.0
        present_coefs = ",".join(sorted(summary["coefs"].keys())) if summary["coefs"] else "<none>"
        mode = "STRICT" if args.strict else "OK"
        print(
            f"[{mode}] {path} -> tau1={tau1:.4f} tau2={tau2:.4f} temperature={temperature:.3f} coefs={present_coefs}"
        )
    return 1 if had_error else 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
