# Operations Guide (Runbook)

Short, repeatable ops steps for running FRAM locally and keeping calibration + memory healthy.

## Start session (always-on bootstrap)

PowerShell:

```powershell
.\scripts\start_session.ps1 -Window 5
```

Optional:
- Add `-Warmup` to run `tools/session_warmup.py --json`.
- Add `-Summary` to run `tools/cognitive_memory_summary.py`.
- Add `-RecentDocs` to list recently edited docs (`--hours 48 --limit 25`).
- Add `-SessionId <id>` to set `COGMEM_SESSION_ID`.

## Start the server (Windows)

PowerShell:

```powershell
.\scripts\dev_run.ps1
```

Optional:
- Add `-EnableDevProfile` only for an intentional development-profile run.
- Add `-EnableAutolog` only when cognitive turn persistence is intended.
- Add `-Reload` only while actively editing server code.
- Set `FRAM_STORAGE_ROOT` before launch to override the profile-local runtime.
- Enable capsules: `FRAM_MEMORY_CAPSULE_ENABLED=1`
- Use semantic memory embeddings: `FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=semantic`

## Auto-start on login (always-on)

PowerShell:

```powershell
.\scripts\enable_autostart.ps1
```

Disable:

```powershell
.\scripts\disable_autostart.ps1
```

## Pause/resume for manual backups

Pause the server before copying to external drives:

```powershell
.\scripts\pause_fram.ps1
```

Resume after backups:

```powershell
.\scripts\resume_fram.ps1
```

## Autowire turn capture (cognitive + capsule)

Logs one user+assistant turn into cognitive memory and writes a capsule snapshot.

PowerShell (example):

```powershell
$env:COGMEM_SESSION_ID='always-on'; $env:COGMEM_USER_TMP='hello'; $env:COGMEM_ASSISTANT_TMP='hi'; $env:FRAM_MEMORY_CAPSULE_ENABLED=1; python tools/autowire_turn.py
```

Optional observability:
- Append a machine-readable acknowledgment to `logs/fram_write_ack.jsonl`.
- Set `COGMEM_ECHO_ACK=1` to print the ack JSON to stdout.

Optional tags:
- Set `COGMEM_TAGS="decision,action"` to tag the turn.
- Or prefix text with `@decision`, `@commit`, `@action`, or `@todo` to auto-tag.
- Auto experiment logs: set `COGMEM_EXPERIMENT_AUTO=1` and include `Experiment:` / `Decision:` lines in the turn.
- Capsule cadence: set `COGMEM_CAPSULE_EVERY_N=5` to write every Nth turn; `COGMEM_CAPSULE_TAGS="decision,commitment"` forces snapshots on tagged turns.
- Cadence warnings: `logs/cogmem_autolog_warnings.jsonl` (override with `COGMEM_WARN_LOG`).

## Experiment log (self-improvement loop)

Log a structured experiment into cognitive memory:

```powershell
python tools/experiment_log.py --title "Capsule cadence test" --hypothesis "Frequent snapshots improve recall" --method "Log every turn for 30 turns" --result "Recall improved" --decision "Keep cadence=per-turn" --tags "experiment,decision" --json
```

Add a capsule snapshot of the experiment:

```powershell
python tools/experiment_log.py --title "Capsule cadence test" --decision "Keep cadence=per-turn" --write-capsule --working-session-id always-on --json
```

Interactive mode:

```powershell
python tools/experiment_log.py --interactive --json
```

Summarize experiments:

```powershell
python tools/experiment_summary.py --limit 10
```

Export a markdown digest:

```powershell
python tools/experiment_export.py --limit 10
```

The latest digest shows up in `/ui/observability` under Experiment Digest.
Use `/ui/experiments` for filtered experiment review.

Export a weekly refactor checklist:

```powershell
python tools/refactor_checklist.py
```

## Calibration refresh (recommended)

Runs harvest -> backfill -> slice -> fit -> lint -> status:

```powershell
make refresh-calibration
```

Preview only:

```powershell
python tools/refresh_calibration.py --dry-run
```

Add optional prompt sets or backup:

```powershell
python tools/refresh_calibration.py --include-layout --include-diary --backup
```

## Docs + corpus refresh

```powershell
make refresh-docs
```

## Tests (fast vs slow)

```powershell
pytest -q -m "not slow"
```

```powershell
pytest -q -m slow --durations=20 --durations-min=1.0
```

## Weekly regression runbook (self-improvement loop)

1) Capture experiment + memory summaries:

```powershell
python tools/experiment_summary.py --limit 20
python tools/cognitive_memory_summary.py --json
python tools/weekly_regression_snapshot.py --digest
python tools/refactor_checklist.py
```

2) Run fast tests:

```powershell
pytest -q -m "not slow"
```

3) Optional: slow suite + capsule demo

```powershell
pytest -q -m slow --durations=20 --durations-min=1.0
python tools/run_capsule_demo.py --tag weekly
```

## Weekly regression task (auto)

Enable scheduled weekly snapshots:

```powershell
.\scripts\enable_weekly_regression.ps1 -Day Sunday -Time 09:00
```

Disable:

```powershell
.\scripts\disable_weekly_regression.ps1
```

## Observability quick checks

- Browser: `http://127.0.0.1:8000/ui/observability`
- Experiments: `http://127.0.0.1:8000/ui/experiments`
- Memory summary: `python tools/cognitive_memory_summary.py`

## Session closeout

```powershell
python tools/closeout_guard.py
```

## Storage + artifacts

- `storage/` is local and untracked by git.
- Save run reports in `artifacts/observability/` with clear labels.
