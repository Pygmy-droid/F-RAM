from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_eval.fractal_falsification import (
    ScoreConfig,
    aggregate_seed_results,
    run_falsification,
)


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _extract_seed_runs(payload: Dict[str, object]) -> Dict[str, Dict[str, dict]]:
    seed_runs_raw = payload.get("seed_runs")
    if isinstance(seed_runs_raw, dict):
        return {
            str(seed): runs
            for seed, runs in seed_runs_raw.items()
            if isinstance(runs, dict)
        }
    systems_raw = payload.get("systems")
    config_raw = payload.get("config")
    if isinstance(systems_raw, dict) and isinstance(config_raw, dict):
        seed = config_raw.get("seed")
        if seed is not None:
            return {str(seed): systems_raw}
    return {}


def merge_payloads(paths: Sequence[Path]) -> Dict[str, object]:
    merged_seed_runs: Dict[str, Dict[str, dict]] = {}
    warnings: List[str] = []
    config: Dict[str, object] = {}
    sources: List[str] = []

    for idx, path in enumerate(paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources.append(str(path))
        if idx == 0 and isinstance(payload.get("config"), dict):
            config = dict(payload["config"])
        elif isinstance(payload.get("config"), dict) and payload.get("config") != config:
            warnings.append(f"config mismatch in {path}")

        seed_runs = _extract_seed_runs(payload)
        for seed, systems in seed_runs.items():
            if not isinstance(systems, dict):
                continue
            seed_bucket = merged_seed_runs.setdefault(seed, {})
            for system, results in systems.items():
                if system in seed_bucket:
                    warnings.append(f"duplicate seed {seed} system {system} in {path}")
                    continue
                seed_bucket[system] = results

    config = dict(config)
    config["seeds"] = sorted({int(seed) for seed in merged_seed_runs.keys() if str(seed).isdigit()})
    config.pop("seed", None)
    aggregate = aggregate_seed_results(list(merged_seed_runs.values()))
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "systems": {},
        "seed_runs": merged_seed_runs,
        "aggregate": aggregate,
        "merge_sources": sources,
    }
    if warnings:
        payload["merge_warnings"] = warnings
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fractal falsification harness.")
    parser.add_argument(
        "--systems",
        default="logistic,henon,lorenz",
        help=(
            "Comma-separated systems (logistic, henon, lorenz, aizawa). "
            "Default: logistic,henon,lorenz."
        ),
    )
    parser.add_argument("--count", type=int, default=12, help="Trajectories per system.")
    parser.add_argument("--steps", type=int, default=64, help="Steps per trajectory.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument(
        "--seeds",
        default=None,
        help="Comma-separated seeds to sweep (overrides --seed).",
    )
    parser.add_argument("--n-nodes", type=int, default=128, help="Nodes per fractal trace.")
    parser.add_argument("--downsample", type=int, default=128, help="Downsample target for scoring.")
    parser.add_argument("--alpha", type=float, default=0.4, help="Cosine/soft-DTW blend weight.")
    parser.add_argument(
        "--quat-weight",
        type=float,
        default=0.2,
        help="Quaternion weighting when influence is enabled.",
    )
    parser.add_argument(
        "--quat-use-lambda",
        action="store_true",
        help="Use lambda-weighted quaternion alignment (default true).",
    )
    parser.add_argument(
        "--no-quat-use-lambda",
        action="store_true",
        help="Disable lambda weighting in quaternion alignment.",
    )
    parser.add_argument(
        "--ablations",
        default="shuffle_nodes,reverse_nodes,random_coords,random_quat,flat_quat,flat_lambda",
        help="Comma-separated ablation modes.",
    )
    parser.add_argument(
        "--merge",
        default=None,
        help="Comma-separated JSON payloads to merge instead of running a sweep.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("storage/observability/fractal_falsification.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.merge:
        merge_paths = [Path(item) for item in _parse_list(args.merge)]
        payload = merge_payloads(merge_paths)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return
    systems = _parse_list(args.systems)
    ablations = _parse_list(args.ablations)
    seed_values = [int(args.seed)]
    if args.seeds:
        seed_values = [int(item) for item in _parse_list(args.seeds)]
    quat_use_lambda = True
    if args.no_quat_use_lambda:
        quat_use_lambda = False
    elif args.quat_use_lambda:
        quat_use_lambda = True

    config_classic = ScoreConfig(
        alpha=float(args.alpha),
        quat_weight=float(args.quat_weight),
        quat_use_lambda=quat_use_lambda,
        quat_influence=False,
        downsample_target=int(args.downsample),
    )
    config_quat = ScoreConfig(
        alpha=float(args.alpha),
        quat_weight=float(args.quat_weight),
        quat_use_lambda=quat_use_lambda,
        quat_influence=True,
        downsample_target=int(args.downsample),
    )

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "count": int(args.count),
            "steps": int(args.steps),
            "seed": int(args.seed),
            "n_nodes": int(args.n_nodes),
            "downsample": int(args.downsample),
            "alpha": float(args.alpha),
            "quat_weight": float(args.quat_weight),
            "quat_use_lambda": bool(quat_use_lambda),
            "ablations": ablations,
        },
        "systems": {},
    }
    if len(seed_values) > 1:
        payload["config"]["seeds"] = seed_values

    if len(seed_values) == 1:
        for system in systems:
            results = run_falsification(
                system,
                count=int(args.count),
                steps=int(args.steps),
                seed=seed_values[0],
                n_nodes=int(args.n_nodes),
                config_classic=config_classic,
                config_quat=config_quat,
                ablations=ablations,
            )
            payload["systems"][system] = results
    else:
        seed_runs: dict[str, dict] = {}
        for seed in seed_values:
            system_results: dict[str, dict] = {}
            for system in systems:
                system_results[system] = run_falsification(
                    system,
                    count=int(args.count),
                    steps=int(args.steps),
                    seed=seed,
                    n_nodes=int(args.n_nodes),
                    config_classic=config_classic,
                    config_quat=config_quat,
                    ablations=ablations,
                )
            seed_runs[str(seed)] = system_results
        payload["seed_runs"] = seed_runs
        payload["aggregate"] = aggregate_seed_results(list(seed_runs.values()))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
