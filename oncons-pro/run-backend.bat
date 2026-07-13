@echo off
cd /d "%~dp0backend"
echo.
echo Starting OnCons backend at http://127.0.0.1:8000
"%~dp0backend\.venv312\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
