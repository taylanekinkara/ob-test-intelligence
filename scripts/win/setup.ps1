$ErrorActionPreference = "Stop"
$BaseDir = Split-Path -Parent $PSScriptRoot

Write-Host "ob-test-intelligence setup" -ForegroundColor Cyan

if (-not (Test-Path "$BaseDir\.venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv "$BaseDir\.venv"
}

$pip = "$BaseDir\.venv\Scripts\pip.exe"
$python = "$BaseDir\.venv\Scripts\python.exe"

Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $pip install -r "$BaseDir\requirements.txt" --quiet

if (-not (Test-Path "$BaseDir\.env")) {
    Copy-Item "$BaseDir\.env.example" "$BaseDir\.env"
    Write-Host "Created .env from .env.example - edit if needed" -ForegroundColor Yellow
}

Write-Host "Running smoke test..." -ForegroundColor Yellow
$env:PYTHONPATH = "$BaseDir\src"
& $python -m app.cli smoke

Write-Host "Setup complete!" -ForegroundColor Green
