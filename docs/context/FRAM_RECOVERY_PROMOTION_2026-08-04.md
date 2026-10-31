# F-RAM canonical rescue promotion

## CLAIM

```text
CLAIM FRAM-PROMOTE-20260804-1130
timestamp: 2026-08-04 11:30:23 +02:00
owner: Aurora (Codex lead)
base commit: 95c174ff3d6a0a9db6d80c435f4f4348fe8ccc17
branch: firelink/full-merge
worktree: D:\Dev\_firelink_recovered_20260804
scope: promote the independently verified complete-history rescue into a new NVMe canonical sibling and refresh its canonical coordinates
exact write paths/globs: AGENTS.md; docs/context/HOT_CONTEXT.md; docs/context/FRAM_RECOVERY_PROMOTION_2026-08-04.md; docs/CODEX_DIARY.md; docs/F-RAM-roadmap.md; matching tracked docs-ingest mirrors
preserved invariants: damaged D:\Dev\_firelink_merge remains read-only evidence; protected D:\Dev\FRAM_V22_Starter\fram_v22_starter remains untouched; no history rewrite; Hopf and fractal gates unchanged
exit gate: canonical branch at sealed evaluation commit; new coordinates pass context validation; fsck/NUL/compile/diff/closeout checks pass; focused test batches pass; worktree clean
status: ACTIVE
```

## Evidence before coordinate refresh

- Source bundle SHA-256:
  `F13ADBCF612CF50FE5A37F349B6CD5C94FC71C9AB51C5F6E9912D51C8FCBF362`.
- `git bundle verify` reported complete history.
- The D: archive copy hash matched the source bundle before cloning.
- The independent clone passed `git fsck --full --no-reflogs --no-dangling`.
- `firelink/full-merge` fast-forwarded from `aea554e` to `95c174f`.
- Promotion test batches passed: 12 focused evaluation, 17
  orchestrator/serving, and 38 existing evaluation regression tests.
- The corrupted predecessor and protected live tree were read only for status
  evidence and received no writes.

## Coordination blind edge

`D:\Dev\firelink.md` is readable but its ACL grants Rick only read/synchronize
access. The append-only claim could not be added without changing permissions.
This tracked packet preserves the claim without rewriting, transcoding, or
changing ACLs on the atlas.

## CLAIM - full-suite closeout defects

```text
CLAIM FRAM-CLOSEOUT-20260804-1238
timestamp: 2026-08-04 12:38 +02:00
owner: Aurora (Codex lead)
base commit: 7dca8292edaaa507282373e0615e7be419a999b3
branch: firelink/full-merge
worktree: D:\Dev\_firelink_recovered_20260804
scope: fix the fresh-corpus hierarchy and confidence failures exposed by the canonical full-suite run, plus the exact-token candidate truncation edge exposed by their focused rerun
exact write paths/globs: scripts/ingest_project_docs.py; fram_core/pipeline.py; fram_core/calibrate.py; tools/calibration_lint.py; tests/test_ingest_project_docs.py; tests/test_pipeline_orchestrator.py; tests/test_calibrate.py; tests/test_calibration_lint_cli.py; tests/test_calibration_status_cli.py; docs/Architecture.md; docs/CODEX_DIARY.md; docs/F-RAM-roadmap.md; docs/context/FRAM_RECOVERY_PROMOTION_2026-08-04.md; matching tracked docs-ingest mirrors
preserved invariants: corrected confidence feature signs from spec section 5; append-only provenance; protected and damaged predecessor trees remain untouched
exit gate: BOM hierarchy regression passes; invalid negative-g calibration is rejected; exact content-token overlap survives candidate-budget truncation; Aria, Puffin, and hierarchy regressions pass on fresh-corpus state; focused tests and full suite pass; generated runtime artifacts restored; worktree clean
status: ACTIVE
```
