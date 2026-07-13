$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv312\Scripts\python.exe"

if (!(Test-Path $Python)) {
    Write-Host "Python 3.12 venv was not found at:" -ForegroundColor Red
    Write-Host $Python
    Write-Host ""
    Write-Host "Install Python 3.12 or recreate backend\.venv312, then run this again."
    exit 1
}

Write-Host "Using Python:" -ForegroundColor Cyan
& $Python --version

Write-Host ""
Write-Host "Checking backend imports..." -ForegroundColor Cyan
Push-Location $Backend
& $Python -c "from app.main import app; print(app.title)"
Pop-Location

Write-Host ""
Write-Host "Starting backend and frontend..." -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:5500"
Write-Host ""

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "Set-Location -LiteralPath '$Backend'; & '$Python' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "Set-Location -LiteralPath '$Frontend'; & '$Python' -m http.server 5500"
)

Write-Host "Open this URL in your browser:" -ForegroundColor Green
Write-Host "http://localhost:5500"
