@echo off
cd /d "%~dp0"
start "OnCons Backend" "%~dp0run-backend.bat"
timeout /t 5 /nobreak >nul
start "OnCons Frontend" "%~dp0run-frontend.bat"
echo.
echo OnCons is starting.
echo Open http://localhost:5500 in your browser.
pause
