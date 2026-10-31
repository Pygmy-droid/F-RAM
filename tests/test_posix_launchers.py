"""Execute Bash launchers against fake Python, without installing or serving."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")
pytestmark = pytest.mark.skipif(
    not BASH, reason="Bash required for POSIX launcher contracts"
)


@pytest.fixture
def launcher(tmp_path):
    root = tmp_path / "checkout with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("bootstrap_env.sh", "dev_run.sh", "make_it_work.sh"):
        (scripts / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    fake = root / ".venv" / "bin" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'printf "CALL" >> "$FRAM_TEST_CAPTURE"\n'
        'printf "|%s" "$@" >> "$FRAM_TEST_CAPTURE"\n'
        'printf "\\nENV|%s|%s|%s\\n" "${FRAM_DEV_PROFILE:-}" '
        '"${COGMEM_AUTOLOG:-}" "${FRAM_STORAGE_ROOT:-}" >> "$FRAM_TEST_CAPTURE"\n'
        'if [[ "$1" == -c && "${FRAM_TEST_BAD_VERSION:-0}" == 1 ]]; then exit 1; fi\n',
        encoding="utf-8",
        newline="\n",
    )
    fake.chmod(0o755)
    capture = tmp_path / "calls.txt"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("FRAM_", "COGMEM_", "MCP_"))
    }
    env.update(FRAM_TEST_CAPTURE=capture.as_posix(), HOME=tmp_path.as_posix())

    def run(script="dev_run.sh", args=(), overrides=None):
        result = subprocess.run(
            [BASH, str(scripts / script), *args],
            cwd=tmp_path,
            env={**env, **(overrides or {})},
            capture_output=True,
            text=True,
            timeout=20,
        )
        calls = capture.read_text(encoding="utf-8") if capture.exists() else ""
        return result, calls

    return run, root


def test_default_launch_is_loopback_and_disables_inherited_logging(launcher):
    run, _ = launcher
    result, calls = run(overrides={"FRAM_DEV_PROFILE": "1", "COGMEM_AUTOLOG": "1"})
    assert result.returncode == 0, result.stderr
    assert (
        "CALL|-m|uvicorn|fram_serving.app:app|--host|127.0.0.1|--port|8000|--reload"
        in calls
    )
    assert "ENV|0|0|" in calls
    assert "/.fram/runtimes/fram_v22_starter/storage" in calls


def test_explicit_launch_options_and_storage_spaces(launcher):
    run, _ = launcher
    result, calls = run(
        args=(
            "--port",
            "8017",
            "--no-reload",
            "--storage-root",
            "new runtime",
            "--enable-autolog",
            "--enable-dev-profile",
        )
    )
    assert result.returncode == 0, result.stderr
    assert "|--port|8017" in calls and "--reload" not in calls
    assert "ENV|1|1|" in calls and "/new runtime" in calls


@pytest.mark.parametrize("token", ["", "short", " " * 40, "change-me"])
def test_external_bind_refuses_missing_weak_or_placeholder_token(launcher, token):
    run, _ = launcher
    result, calls = run(
        args=("--bind-host", "0.0.0.0"), overrides={"MCP_BEARER": token}
    )
    assert result.returncode != 0
    assert not calls


def test_placeholder_refused_even_on_loopback(launcher):
    run, _ = launcher
    result, calls = run(overrides={"MCP_BEARER": "change-me"})
    assert result.returncode != 0 and not calls


def test_explicit_external_bind_with_token_never_prints_token(launcher):
    run, _ = launcher
    token = "synthetic-long-token-for-launcher-test-only"
    result, calls = run(
        args=("--bind-host", "0.0.0.0"), overrides={"MCP_BEARER": token}
    )
    assert result.returncode == 0, result.stderr
    assert "|--host|0.0.0.0" in calls
    assert token not in result.stdout + result.stderr + calls


@pytest.mark.parametrize("port", ["0", "65536", "8000;echo bad", "-1"])
def test_invalid_port_never_launches(launcher, port):
    run, _ = launcher
    result, calls = run(args=("--port", port))
    assert result.returncode != 0 and not calls


def test_setup_does_not_hydrate_or_start_server(launcher):
    run, _ = launcher
    result, calls = run("make_it_work.sh")
    assert result.returncode == 0, result.stderr
    assert "CALL|-m|pip|install|-e|.|-r|requirements-dev.txt" in calls
    assert "CALL|-m|pip|check" in calls
    assert "uvicorn" not in calls and "bootstrap_memory" not in calls


def test_setup_explicit_start_preserves_optins(launcher):
    run, _ = launcher
    result, calls = run("make_it_work.sh", ("--start-server", "--enable-autolog"))
    assert result.returncode == 0, result.stderr
    assert "CALL|-m|uvicorn" in calls and "ENV|0|1|" in calls


def test_bad_interpreter_stops_before_install(launcher):
    run, _ = launcher
    result, calls = run("make_it_work.sh", overrides={"FRAM_TEST_BAD_VERSION": "1"})
    assert result.returncode != 0
    assert "CALL|-m|pip" not in calls


def test_copied_windows_environment_is_not_replaced(launcher):
    run, root = launcher
    (root / ".venv" / "bin" / "python").unlink()
    result, calls = run("make_it_work.sh")
    assert result.returncode != 0 and not calls
    assert "fresh checkout" in result.stderr
