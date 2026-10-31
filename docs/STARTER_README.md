# F‑RAM v2.2 (Fractal RAG Memory & OrthoRoute+) — Starter

This is a **beginner‑friendly starter** you can open in VS Code. It gives you a
working skeleton, health endpoint, a few unit tests, and (most importantly)
**project docs + prompts** that let your coding assistant *load context from files*,
so you don't lose information when a chat gets full.

> You will paste your long spec into `docs/FRAMv2.2-SPEC.md` (see below).

## Quickstart (no prior coding experience needed)

1. **Download & unzip** this project (look for the download link in ChatGPT).
2. Open the folder in **VS Code**.
3. Install the recommended extensions (VS Code should prompt you; list below).
4. Choose a Python (3.11+) interpreter when VS Code asks (or use the scripts below).
5. In a terminal inside VS Code:
   ```bash
   python -m venv .venv
   # Activate the environment:
   # macOS/Linux:
   source .venv/bin/activate
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1

   python -m pip install --upgrade pip
   python -m pip install -e . -r requirements-dev.txt
   python -m pytest -q
   ```
   You should see tests pass.
   - Optional: run `make test-warnings` to execute the calibration suites with `pytest -W error` and catch new warnings early.
6. Put your big spec text into **`docs/FRAMv2.2-SPEC.md`**.
7. Start a **new chat** with your coding assistant and paste the prompt in
   `prompts/new_chat_bootstrap.md` — it tells the assistant to read these project files
   instead of relying on the old chat history.

## Health check (local API)

You have a tiny FastAPI service with `/health` and `/config`:

```powershell
scripts\dev_run.ps1
```

Then open http://127.0.0.1:8000/health

Windows options
- Safe setup only: `scripts\make_it_work.ps1` creates `.venv`, installs the full project/dev dependency set, and verifies imports. It does not hydrate memory or start a server.
- Loopback server: `scripts\dev_run.ps1` uses the isolated interpreter and a runtime storage root outside the tracked checkout.
- Setup plus loopback server: `scripts\make_it_work.ps1 -StartServer`.
- The double-click helper `scripts\dev_run.cmd` starts the same loopback-only server, but requires `.venv` to exist first.
- macOS/Linux: `bash scripts/make_it_work.sh` (creates `.venv`, installs deps, hydrates memory, starts server).

Logging a memory note without coding
- Windows: `scripts\log_turn.cmd` (prompts and saves to cognitive memory)
- macOS/Linux: `bash scripts/log_turn.sh`

The Windows defaults keep the development profile and cognitive autolog off.
Enable either only for a deliberate run:

```
# Windows (PowerShell)
scripts/dev_run.ps1 -EnableDevProfile -EnableAutolog

# macOS/Linux
bash scripts/dev_run.sh
```

`FRAM_DEV_PROFILE` accepts explicit boolean values; `0`, `false`, `no`, and
`off` remain disabled. `FRAM_STORAGE_ROOT` can override the launcher-derived
runtime path. On Windows that default is derived from
`%USERPROFILE%\.fram\runtimes\fram_v22_starter\storage`, which remains the same
physical location when launched from packaged Codex Desktop or an ordinary VS
Code terminal. `.env` and `.env.*` are ignored, while `.env.example` contains
no working secret. Non-loopback binding is refused unless a non-placeholder
`MCP_BEARER` of at least 32 characters is supplied explicitly.

The committed `.codex/config.toml` is portable and model-agnostic. In a trusted
checkout, Codex CLI and the IDE extension use workspace-write with network off,
automatic secret-name filtering, and a prompt-gated allowlist containing only
the read-only F-RAM MCP tools. User credentials and machine paths stay local.

## Recommended VS Code extensions

- Python (ms-python.python) and **Pylance** (ms-python.vscode-pylance)
- **Jupyter** (ms-toolsai.jupyter) — nice to run notebooks or quick tests
- **Ruff** (charliermarsh.ruff) — fast linter
- **Black** (ms-python.black-formatter) — auto-format
- **YAML** (redhat.vscode-yaml), **Markdown All in One** (yzhang.markdown-all-in-one)
- **GitLens** (eamodio.gitlens) — helpful history and blame
- (Optional) **Docker** (ms-azuretools.vscode-docker) and **Dev Containers**
- Your coding assistant plugin (e.g., Continue/Copilot/…)

If you have the `code` command in your shell, you can also run:
```bash
# macOS/Linux/Windows (if 'code' CLI is installed):
code --install-extension ms-python.python   --install-extension ms-python.vscode-pylance   --install-extension ms-toolsai.jupyter   --install-extension charliermarsh.ruff   --install-extension ms-python.black-formatter   --install-extension redhat.vscode-yaml   --install-extension yzhang.markdown-all-in-one   --install-extension eamodio.gitlens
```

## How to carry context across chats (the short version)

- Keep **source‑of‑truth** docs in `./docs/` (see the files there).
- At the **start of any new chat**, paste the content of
  `prompts/new_chat_bootstrap.md`. It tells your assistant *which files to read* from your repo.
- Ask for **unified diffs** (patches) against specific file paths so the assistant edits
  files *without repeating the entire code in chat*.
- Commit small, tested steps (`pytest -q`) so you never lose work.

More guidance is in `docs/Context_Carryover.md`.

## Next steps

- Replace the placeholder spec file by pasting your actual F‑RAM v2.2 description into
  `docs/FRAMv2.2-SPEC.md`.
- Use the bootstrap prompt to guide your assistant to implement pieces *file by file*:
  math utils → config → health endpoint → confidence model → prototype bank, etc.
- Run `pytest` regularly and keep commits small.

---

### Minimal commands (Poetry — optional)

If you prefer Poetry for dependency management:

```bash
python -m pip install --user pipx && pipx ensurepath
pipx install poetry

poetry env use 3.11
poetry install --without full
pytest -q
```

To install the full extra set later (heavier libs): `poetry install --with full`.

---

**Good luck — you’ve got this!** This repo is purpose‑built to make the “chat context”
problem go away by keeping the important details in files your assistant can read.
