# Phase C - Initialization Plan

## Objectives
- Lock clean rails between /search, /rank, /beliefs, /observability.
- Add calibration scripts and recall reporting with audit log.
- Fold fractal recall metrics into Phase C so calibration, CLI reporting, and observability stay in sync.

## Deliverables
- scripts/calibrate_phase_c.py
- scripts/recall_report_phase_c.py
- Observability: recall_report v0 wiring
- Fractal recall summary surfaced via CLI + `/observability/recall_report`
- Version bump: 22.1.0

## Milestones
- C1: wire build_situation + audit log
- C2: calibrate relevance/routing on 10-20 seed tasks
- C3: recall_report surfaces coverage, conflicts, drift

## Exit Criteria
- All endpoints green locally (uvicorn)
- Recall report shows � baseline coverage with no regressions plus fractal recall stats.
