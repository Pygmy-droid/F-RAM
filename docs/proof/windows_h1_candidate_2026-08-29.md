# Windows H1 Checkpoint Verification - 2026-08-29

Status: **accepted H1 checkpoint**. Rick explicitly accepted the verified
Windows candidate on 2026-08-29 at 22:22 SAST. Push, real visual-seed canary
promotion, network exposure, and Mac reproduction remain separate decisions.

## Authority chain

- Sealed F baseline (`H0`):
  `8b4e06e3a2a08dcd3391b77bf2393500bf89e7e8`.
- Local annotated H0 tag: `fram-v22-h0-20260829`.
- Fully tested Windows code checkpoint:
  `d6674487d05e4462dff5ca2e183f5cc2c8df571c` on
  `codex/windows-integration-20260829`.
- Local annotated accepted-H1 tag: `fram-v22-h1-windows-20260829`. It points
  to the acceptance commit containing this receipt; the fully tested code
  checkpoint above remains its code-bearing ancestor.
- Custody receipt SHA-256:
  `DE563BF3BB20CDB568B595AED23990AC75DD463D39315F746759A70CCFCBA226`.
- Legacy C remained frozen at
  `c4a7bef21164c1110cda192502cf0c28e4d2c57c`: zero tracked changes,
  615 untracked entries, two stashes, and protected local `autoflip-eval` at
  `468f1e4399244a05786ba84f34be2b0ee5b09777`.
- F remained at H0 with its existing 18 tracked and four untracked changes.
  None of those source-tree changes entered the integration branch.

## Integrated commits

1. `53b58df0205b78c495c0057966b617c3c7a5a4ed` - bounded, privacy-minimal
   visual-seed candidate evaluator and tests.
2. `e24db0e3379960b2c9a80f1ce65f4d09549ce093` - visual-seed custody,
   authority, and canary documentation.
3. `1f6acf08f0eebcb604bea3fa7dc0b5a68cba4fcd` - isolated Python runtime,
   portable Codex/VS Code defaults, safe Windows launchers, and config tests.
4. `d6674487d05e4462dff5ca2e183f5cc2c8df571c` - one physical runtime root
   across packaged Desktop and ordinary shells, `/config` secret redaction,
   and removal of the obsolete Phase D expected-failure marker.

## Observed validation

- Independent no-hardlink clone of the exact code checkpoint:
  `697 passed in 1192.04s (0:19:52)`.
- Focused config/MCP/serving regression set: `28 passed in 174.97s`.
- Secret-redaction and Phase D set: `8 passed in 34.91s`.
- Ruff syntax/import checks, Black checks, PowerShell parsing, `git diff
  --check`, context-packet validation, `pip check`, and `git fsck` passed.
  `git fsck` reports one unreachable blob and no integrity error.
- The full-suite clone contained the expected 17 generated tracked storage
  changes after testing. Those artifacts stayed quarantined and were not
  staged or committed.
- Python 3.11.9 imports succeeded for the installed F-RAM package, FastAPI,
  MCP, NumPy, scikit-learn, Torch, Transformers, Hugging Face Hub, and Pillow.

## Live Windows seam

- The launcher-derived runtime is machine-local at
  `%USERPROFILE%\.fram\runtimes\fram_v22_starter\storage`; `/config`,
  `/where`, cognitive storage, and lived storage resolved to that one physical
  root from the Desktop-hosted process.
- The service listened only on `127.0.0.1:8000`; health returned `ok`.
- Development profile, cognitive autolog, fractal influence, quaternion
  influence, and MCP cognitive writes remained off.
- The user-wide `FRAM_DEV_PROFILE=1`, `COGMEM_AUTOLOG=1`, and redundant
  `FRAM_FRACTAL_BLEND_ALPHA=0.4` overrides were removed after their prior
  values were recorded. Development profile and autolog now require explicit
  launcher switches; already-running apps retain inherited values until their
  next restart.
- `/config` omitted `api_key` after the security fix.
- MCP initialized as `FRAM v2.2`, advertised nine server tools, and completed a
  read-only `fram.memory_list` call. Project Codex configuration exposes only
  `fram.get_trace_uri`, `fram.memory_list`, `fram.memory_bootstrap`, and
  `fram.memory_get`, with prompt approval.
- One explicitly synthetic H1 probe exercised `/query`: five citations, 226
  finite scores, CELF read limit five, transitional-complexity diagnostics,
  and trace `c937e9b89a6c4b7a849398f5ef5c8188`. Its cognitive and lived records were
  found again after a clean server restart, proving persistence without using
  personal source material.

## Deliberate non-claims and remaining gates

- This evidence proves the tested Windows repository/runtime contract; it does
  not prove every future workload or authorize a production/network exposure.
- The visual-seed evaluator is installed and test-validated, but no real-image
  canary has been promoted. Visual evidence remains derived and has no ranking
  authority.
- The regenerated F corpus/index batch and private cognitive append remain
  outside Git and still need a separate artifact/privacy decision.
- macOS launchers, paths, and parity are intentionally deferred.
- Rick explicitly accepted this Windows checkpoint as H1 on 2026-08-29 at
  22:22 SAST. No remote was configured for writing and no push occurred.
