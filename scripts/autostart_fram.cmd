@echo off
REM Always-on FRAM server (auto-start target).
setlocal
set "REPO_ROOT=%~dp0.."
pushd "%REPO_ROOT%"

if not exist "logs" mkdir "logs"

REM Prefer venv Python if present.
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

REM Env: full capture for always-on use.
set FRAM_DEV_PROFILE=1
set FRAM_MEMORY_CAPSULE_ENABLED=1
set FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=semantic
set FRAM_COGNITIVE_MEMORY_SEMANTIC_MODEL=all-MiniLM-L6-v2
set COGMEM_AUTOLOG=1
set COGMEM_SESSION_ID=always-on
set COGMEM_WORKING_SESSION_ID=always-on

%PYTHON% -m uvicorn fram_serving.app:app --reload --host 127.0.0.1 --port 8000 >> logs\uvicorn.autostart.log 2>&1

popd
endlocal
