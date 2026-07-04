@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%recipe-vault-paddle-ocr\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  set "PYTHON=python"
)

"%PYTHON%" "%SCRIPT_DIR%run-parser-tests.py"
pause
