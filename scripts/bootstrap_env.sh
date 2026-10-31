#!/usr/bin/env bash
# Source this file; profile/autolog require explicit switches on each invocation.
_fram_bootstrap_env() {
  local storage_root="${FRAM_STORAGE_ROOT:-}" dev_profile=0 autolog=0
  while (($#)); do
    case "$1" in
      --storage-root)
        [[ $# -ge 2 && -n "$2" ]] || { echo "--storage-root needs a path" >&2; return 2; }
        storage_root="$2"; shift 2 ;;
      --enable-dev-profile) dev_profile=1; shift ;;
      --enable-autolog) autolog=1; shift ;;
      *) echo "Unknown environment option: $1" >&2; return 2 ;;
    esac
  done
  if [[ -z "$storage_root" ]]; then
    [[ -n "${HOME:-}" ]] || { echo "Set HOME or FRAM_STORAGE_ROOT" >&2; return 2; }
    storage_root="$HOME/.fram/runtimes/fram_v22_starter/storage"
  fi
  # The runtime may not exist yet. Do not create or hydrate it during setup.
  case "$storage_root" in
    /*|[A-Za-z]:/*) ;;
    *) storage_root="$PWD/$storage_root" ;;
  esac
  export FRAM_STORAGE_ROOT="$storage_root"
  export FRAM_DEV_PROFILE="$dev_profile" COGMEM_AUTOLOG="$autolog"
  export COGMEM_SESSION_ID="${COGMEM_SESSION_ID:-dev}"
  export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://127.0.0.1:8000}"
  printf 'F-RAM environment: storage=%s; dev=%s; autolog=%s\n' \
    "$FRAM_STORAGE_ROOT" "$FRAM_DEV_PROFILE" "$COGMEM_AUTOLOG"
}
_fram_bootstrap_env "$@"
