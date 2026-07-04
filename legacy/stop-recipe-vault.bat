@echo off
setlocal
cd /d "%~dp0"
set PYTHON=%~dp0recipe-vault-paddle-ocr\.venv\Scripts\python.exe
if not exist "%PYTHON%" (
  echo Recipe Vault could not find its local Python OCR environment.
  pause
  exit /b 1
)
"%PYTHON%" "%~dp0recipe-vault-local-server.py" --stop
echo Recipe Vault local app stopped.
pause
