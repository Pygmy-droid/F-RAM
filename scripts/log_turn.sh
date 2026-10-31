#!/usr/bin/env bash
set -euo pipefail

# Simple helper to append a turn to cognitive memory using tools/autolog_once.py
# Defaults to session "dev" and enables autolog.

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)/.."

PY="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python"
fi

read -rp "Session ID (default: dev): " session
session=${session:-dev}
read -rp "User text: " user
read -rp "Assistant text (optional; Enter to skip): " assistant || true

export COGMEM_AUTOLOG="${COGMEM_AUTOLOG:-1}"
export COGMEM_SESSION_ID="$session"
export COGMEM_USER_TMP="$user"
export COGMEM_ASSISTANT_TMP="${assistant:-}"

"$PY" "$REPO_ROOT/tools/autolog_once.py"
echo "Saved to cognitive memory (session '$session')."

