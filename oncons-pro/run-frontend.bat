@echo off
cd /d "%~dp0frontend"
echo Starting OnCons frontend at http://localhost:5500
"%~dp0backend\.venv312\Scripts\python.exe" -m http.server 5500
pause
