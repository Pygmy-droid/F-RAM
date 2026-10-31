from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


CHECKLIST = [
    "Review latest experiment digest and confirm decisions are captured.",
    "Scan logs/cogmem_autolog_warnings.jsonl for cadence warnings.",
    "Check /ui/observability for recall hit rate + experiment digest freshness.",
    "Run pytest -q -m \"not slow\" (fast suite).",
    "Verify weekly regression snapshot exists under artifacts/observability/.",
    "Update docs/CODEX_DIARY.md with any notable changes.",
]


def export_checklist(out_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Weekly Refactor Checklist",
        f"- Generated: {stamp}",
        "",
        "## Checklist",
    ]
    for idx, item in enumerate(CHECKLIST, start=1):
        lines.append(f"{idx}. [ ] {item}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a weekly refactor checklist markdown file.")
    parser.add_argument("--out", type=Path, default=None, help="Output path for the checklist markdown.")
    args = parser.parse_args()
    out_path = args.out
    if out_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = Path("artifacts") / "observability" / f"refactor_checklist_{stamp}.md"
    export_checklist(out_path)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
