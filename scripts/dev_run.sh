#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
venv_python="$repo_root/.venv/bin/python"
bind_host=127.0.0.1 port=8000
reload_args=(--reload)
env_args=()
while (($#)); do
  case "$1" in
    --bind-host|--port|--storage-root)
      [[ $# -ge 2 && -n "$2" ]] || { echo "$1 needs a value" >&2; exit 2; }
      case "$1" in
        --bind-host) bind_host="$2" ;;
        --port) port="$2" ;;
        --storage-root) env_args+=("$1" "$2") ;;
      esac
      shift 2 ;;
    --enable-dev-profile|--enable-autolog) env_args+=("$1"); shift ;;
    --no-reload) reload_args=(); shift ;;
    --help)
      echo "Usage: bash scripts/dev_run.sh [--port 8000] [--bind-host 127.0.0.1] [--storage-root PATH] [--no-reload] [--enable-dev-profile] [--enable-autolog]"
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ "$port" =~ ^[0-9]{1,5}$ ]] && ((10#$port >= 1 && 10#$port <= 65535)) || {
  echo "Port must be between 1 and 65535" >&2; exit 2;
}
[[ -x "$venv_python" ]] || { echo "Missing POSIX .venv; run bash scripts/make_it_work.sh" >&2; exit 1; }
[[ "${MCP_BEARER:-}" != "change-me" ]] || { echo "Refusing placeholder MCP_BEARER" >&2; exit 2; }
case "$bind_host" in
  127.0.0.1|localhost|::1) ;;
  *)
    token_chars="${MCP_BEARER:-}"
    token_chars="${token_chars//[[:space:]]/}"
    [[ ${#token_chars} -ge 32 ]] || {
      echo "Non-loopback binding requires an explicit MCP_BEARER of at least 32 non-whitespace characters" >&2
      exit 2
    } ;;
esac
cd -- "$repo_root"
source "$repo_root/scripts/bootstrap_env.sh" "${env_args[@]}"
exec "$venv_python" -m uvicorn fram_serving.app:app \
  --host "$bind_host" --port "$port" "${reload_args[@]}"
