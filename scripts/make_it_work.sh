#!/usr/bin/env bash
set -euo pipefail

# Core-only setup; never hydrate memory or start a service implicitly.
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
python_command=python3 start_server=0
env_args=()
while (($#)); do
  case "$1" in
    --python|--storage-root)
      [[ $# -ge 2 && -n "$2" ]] || { echo "$1 needs a value" >&2; exit 2; }
      if [[ "$1" == --python ]]; then python_command="$2"; else env_args+=("$1" "$2"); fi
      shift 2 ;;
    --start-server) start_server=1; shift ;;
    --enable-dev-profile|--enable-autolog) env_args+=("$1"); shift ;;
    --help)
      echo "Usage: bash scripts/make_it_work.sh [--python python3.12] [--storage-root PATH] [--start-server] [--enable-dev-profile] [--enable-autolog]"
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
cd -- "$repo_root"
venv_python="$repo_root/.venv/bin/python"
version_check='import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else "F-RAM requires Python 3.11 or 3.12")'
if [[ ! -x "$venv_python" ]]; then
  # Never replace a copied Windows environment or a damaged existing one.
  [[ ! -e .venv ]] || { echo "Existing .venv is not a POSIX environment; use a fresh checkout" >&2; exit 1; }
  "$python_command" -c "$version_check"
  "$python_command" -m venv .venv
fi
"$venv_python" -c "$version_check"
"$venv_python" -m pip install --upgrade pip
"$venv_python" -m pip install -e . -r requirements-dev.txt
"$venv_python" -m pip check
"$venv_python" scripts/verify_imports.py
source "$repo_root/scripts/bootstrap_env.sh" "${env_args[@]}"
echo "Setup complete. No memory was hydrated; server startup requires --start-server."
if ((start_server)); then
  exec bash "$repo_root/scripts/dev_run.sh" "${env_args[@]}"
fi

