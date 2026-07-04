@echo off
setlocal
set ROOT=%~dp0
set PYTHON=%ROOT%.venv\Scripts\python.exe
"%PYTHON%" -m uvicorn server:app --app-dir "%ROOT%" --host 127.0.0.1 --port 8765
