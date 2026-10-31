# F-RAM: Windows, Betty and ChatGPT web

Prepared 2026-09-10 from Windows H1 lineage `5451423`. This is the portable
launch/MCP checkpoint, not a claim that Linux or ChatGPT web has already passed.
The inherited hot packet/checker still names F canonical H0; H1 authority and
the reviewed later commits are recorded in the coordination claim.

## What is complete and what remains

The 2026-09-08 recovery and score correction are committed. Fractal influence
matched the corrected retrieval baseline rather than clearing its lift margin;
activation remains `KEEP_OFF`. Portability does not change that gate. Source
stores and recovered archives are not installation payloads to merge silently.

The launchers now share the Windows contract: explicit startup, local binding,
separate per-user storage, no setup hydration, profile/autolog off unless
requested. MCP tool metadata distinguishes reads from writes and its config
resource omits `api_key`. See the dated verification receipt for executed checks.

## Betty: inspect, install the core, then verify

Betty remains Linux-only. First confirm the running OS, architecture, Python,
free disk and RAM on Betty herself:

```bash
cat /etc/os-release
uname -m
python3 --version
df -h "$HOME"
free -h
```

Use a fresh checkout of the reviewed code; do not transfer the Windows `.venv`,
local credentials, or runtime directories. Git enforces LF for shell scripts.
The package supports Python 3.11/3.12. If the chosen interpreter's `venv` module
is unavailable, install that interpreter's matching venv package on Mint first.
No OS installation or disk-erasure command is part of this procedure.

```bash
# From the fresh repository root, choose an installed supported interpreter.
bash scripts/make_it_work.sh --python python3.12
.venv/bin/python -m pip check
.venv/bin/python scripts/verify_imports.py

# First run: choose a new empty runtime, separate from eventual personal data.
bash scripts/dev_run.sh --storage-root "$HOME/.fram/demos/portable-check/storage" \
  --port 8017 --no-reload
```

In a second terminal:

```bash
.venv/bin/python scripts/verify_mcp.py --base-url http://127.0.0.1:8017
.venv/bin/python -m pytest -q tests/test_posix_launchers.py tests/test_mcp_metadata_safety.py
```

Stop the foreground server with Ctrl+C. These commands do not install a daemon.
Ordinary later launches default to `$HOME/.fram/runtimes/fram_v22_starter/storage`;
`--storage-root` overrides `FRAM_STORAGE_ROOT`. An explicitly configured runtime
is reused; scripts do not migrate or merge it. Native Mint dependency and locking
tests are still required. Bash-on-Windows testing alone cannot establish those.

Begin with the core hashing backend. Optional visual models, Torch and broad
document extras come after core verification and remain outside ranking authority.
An installed F-RAM server does not also install Diary Hub, Hearth Ledger, or Codex:
each needs its own package, machine-local paths, data backup/restore and MCP test.
Preserve their separate provenance and storage; do not alias them to one database.

## Windows equivalent

```powershell
.\scripts\make_it_work.ps1
$env:FRAM_STORAGE_ROOT = Join-Path $env:USERPROFILE '.fram\demos\portable-check\storage'
.\scripts\dev_run.ps1 -Port 8017 -NoReload
# Second terminal, with the repository virtualenv:
.\.venv\Scripts\python.exe scripts\verify_mcp.py --base-url http://127.0.0.1:8017
```

Development profile and cognitive autolog require explicit switches on each
launcher invocation. Other explicit environment overrides remain operator-owned;
check the selected runtime and influence/write settings before using personal data.

## ChatGPT web: proposed private development connection

Preferred topology:

```text
ChatGPT web -> OpenAI tunnel endpoint -> outbound tunnel client
                                         -> localhost:8017/mcp/
                                         -> isolated F-RAM demo runtime
```

OpenAI documents Secure MCP Tunnel for private development over outbound HTTPS.
It needs a tunnel ID, runtime API key, Platform tunnel permissions and association
with the target ChatGPT workspace. Developer-mode access is separate. It is not
the public plugin distribution route.
[Official tunnel documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

Prepare the isolated local endpoint above first. Obtain the current client from
the official guide's Platform download, run `tunnel-client help quickstart`, and
configure its HTTP upstream as `http://127.0.0.1:8017/mcp/`. Keep runtime secrets
outside Git and chat. Run its doctor before connecting, then keep the client
running. In ChatGPT's developer connection, select Tunnel and the intended tunnel.
Record account visibility, doctor result and actual tool-call evidence; none is
inferred from these local instructions.

Current developer mode supports SSE and streaming HTTP, with OAuth, no-auth or
mixed auth. It accepts these existing tool names; `search`/`fetch` aliases are
not required. Start with `fram.get_trace_uri`, then deliberately enable
`fram.memory_list`/`fram.memory_get` for the synthetic fixture. These latter
tools can initialize missing session metadata and are classified as writes.
[Official developer-mode documentation](https://developers.openai.com/api/docs/guides/developer-mode).

The server still advertises all nine tools. The Codex project allowlist does not
apply to ChatGPT, and toggles/annotations do not implement server-side data scope.
Use only a synthetic runtime for this first connection. A private network path
still transmits returned tool content to ChatGPT. Before personal memory access,
decide exactly which records, users and mutations are authorized and enforce that
scope server-side. Direct public private-data deployments need the documented
OAuth flow; this repository's shared bearer verifier does not implement it.
[Official authentication requirements](https://developers.openai.com/plugins/build/auth).

The verification milestone is the same labelled synthetic fixture retrieved
locally on Windows, locally on Mint, and through ChatGPT, with source/result
receipts retained separately. Then test an explicitly requested synthetic write
and restart recovery. F-RAM query writes traces/archives; bootstrap search logs
telemetry, so neither is marked read-only. Cognitive episode persistence requires
its dual gate; working-memory mutation tools have separate effects.

## Remaining handoff

- Verify Betty's actual Mint installation and available interpreter.
- Run native Linux dependency, launcher, MCP and relevant storage tests.
- Confirm ChatGPT workspace/tunnel access; connect and capture a real tool result.
- Inventory and port the remaining Hearth packages separately.
- Keep real memory migration, fractal activation and unfinished 3D work as
  separately evidenced tasks; this checkpoint does not complete them.
