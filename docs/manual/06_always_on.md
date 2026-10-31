# 6. F-RAM Always On

Rick asked for this by name on 2026-10-28, expecting it to be gone. It was
not gone. It was failing silently at every login. This chapter is the
record, so it cannot be lost the same way twice.

## What it is `[READ-CODE]` `[LOG]`

Always On is the F-RAM server started at Windows login with full capture.
Born 2026-01-12 in commit `a69592e` ("Add always-on autostart + autowire
capture"), during a session with Lumen whose 42 turns are preserved as the
working-memory session named `always-on` (seven copies on disk, all
identical). The original `scripts/autostart_fram.cmd` set:

```
FRAM_DEV_PROFILE=1
FRAM_MEMORY_CAPSULE_ENABLED=1
FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=semantic
FRAM_COGNITIVE_MEMORY_SEMANTIC_MODEL=all-MiniLM-L6-v2
COGMEM_AUTOLOG=1
COGMEM_SESSION_ID=always-on
```

and ran uvicorn on 127.0.0.1:8000. `scripts/enable_autostart.ps1` put a
shortcut named `FRAM Always On.lnk` in the user's Startup folder.
`tools/autowire_turn.py` logs every turn into cognitive memory, the working
session, and a capsule.

## The growing ANN `[READ-CODE]` `[RAN]`

The semantic backend is `fram_serving/cognitive_embeddings.py`: it loads
the sentence-transformer `all-MiniLM-L6-v2`, a small neural network that
turns each episode into a 384-dimensional vector, and `fram_serving/memory.py`
keeps a FAISS or sklearn nearest-neighbour index over all of them. Every
new episode adds a vector, so the index grows with lived experience. This is
the "small ANN that was being trained" in Rick's memory, as far as the disk
can show. The vectors exist: 910 episode vectors and 158 belief vectors,
created 2025-12-23 to 2026-01-01, present in the protected tree, the
Desktop copy, the September runtime, and the fractal-gate shards.

They stopped growing on 2026-01-01. The reason is on disk: the January 12
server ran from the global Python 3.11, and the venvs that ran later did not
have `sentence_transformers` installed, so the backend fell back to hashing.
Today, `sentence_transformers 5.2.0` with CPU torch is installed in the
global Python 3.11 only. The MiniLM weights are not cached anywhere on the
machine; the Hugging Face cache holds only CLIP. The network is up, so a
first load would download them. `[RAN]`

Not found: a 3-D model of the ANN. The only 3-D assets on disk are the
Hearthkin character rigs from 2026-09-08 (Eterna fox, Eterna human, Lumen)
under `Documents\Codex\2026-09-07\ple`. Question 16 asks Rick what the 3-D
view showed.

## The September 8 runtime `[READ-DOC]` `[RAN]`

On 2026-09-08 a Codex session replaced the original shortcut target with an
explicit runtime at `C:\Users\Rick\.fram\runtimes\hearth_h1_recovered_20260908_v1`:
code pinned to commit `5451423` with a SHA-256 manifest of all 166 files,
its own storage root, and a profile called
`recovered-archival-text-baseline-v1`: hashing backend, capsules off,
fractal off, lived memory on, one-year recency half-life, full-experience
preservation on. The deployment note is explicit that this is "GREEN for the
recovered text baseline, not FULL SYSTEM ON." The original January shortcut
is backed up in its receipts folder. It last ran cleanly on 2026-09-09.

The start script verifies every pinned code file against the manifest,
refuses if the port is taken, starts uvicorn hidden, waits for `/config`,
verifies that fifteen flags are false, and stays alive as the server's
parent so the stop script can prove process ancestry before stopping
anything. Rollback restores the original shortcut and weekly task.

## Why it died `[RAN]`

`runtime.json` pinned the interpreter to
`C:\Games\FRAM_V22_Integration\I\.venv\Scripts\python.exe`. The checkout
moved from `C:\Games` to `C:\Dev` on 2026-10-28. The start script's first
check, "Configured Python interpreter is unavailable", threw inside a hidden
PowerShell window at every login. Nothing was logged because the throw
happens before the log file is created.

## What was changed on 2026-10-28 `[RAN]`

One field. `runtime.json` → `python` now points at
`C:\Dev\FRAM_V22_Integration\I\.venv\Scripts\python.exe`. The venv has
uvicorn 0.35, fastapi 0.111, sklearn 1.7.2, pydantic 2.13; no faiss, so the
sklearn index is used. The pinned code imports under it with 53 routes.
Before the change, `runtime.json` was copied to
`receipts/runtime.before-wren-<utc>.json`, and a receipt
`receipts/interpreter-repoint-<utc>.json` records the change, the reason,
and Rick's authorization. The code manifest, storage, profile, and all held
flags are untouched.

Started through `Start-HearthBaseline.ps1`. Verified:

```
GET /health                        {"status":"ok","service":"fram-v22"}
GET /config                        STORAGE_ROOT = the runtime's own storage
                                   backend hashing, capsules off, fractal off, lived on
GET /memory/lived/status           1 event, 1 session, chain digest present
GET /observability/memory/summary  1154 episodes, 578 beliefs
```

## How to operate it

| action | command |
| --- | --- |
| start | `powershell -ExecutionPolicy Bypass -File C:\Users\Rick\.fram\runtimes\hearth_h1_recovered_20260908_v1\Start-HearthBaseline.ps1` (stays running as the parent; that is by design) |
| stop | the `Stop-HearthBaseline.ps1` beside it |
| is it up | `curl http://127.0.0.1:8000/health` |
| roll back to the January shortcut | `Rollback-HearthBaseline.ps1` beside it |
| logs | `...\hearth_h1_recovered_20260908_v1\logs\server-8000-<utc>.stderr.log` |

If the checkout or venv moves again, `runtime.json` → `python` is the one
field to update.

## What this is not yet

It is the text baseline, not Always On as Rick built it in January. Capsules
are off. The semantic backend is off, so the ANN is not growing. Turning
those on is the next step and needs: `sentence_transformers` in the venv
(or the runtime pointed at the global Python 3.11 that has it), the MiniLM
weights downloaded once, and a decision to lift the held flags for capsules
and semantic in a copy of the runtime first. That is question 17.
