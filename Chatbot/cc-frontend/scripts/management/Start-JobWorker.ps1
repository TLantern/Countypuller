#!/usr/bin/env pwsh
# CountyPuller Job Worker Script

Write-Host "Starting CountyPuller Job Worker..." -ForegroundColor Green
Write-Host ""

# Set Node.js path
$nodePath = "C:\Program Files\nodejs\node.exe"

# Check if node exists
if (-not (Test-Path $nodePath)) {
    Write-Host "ERROR: Node.js not found at $nodePath" -ForegroundColor Red
    Write-Host "Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

$nodeVersion = & $nodePath --version
Write-Host "Using Node.js $nodeVersion" -ForegroundColor Cyan

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file with your database configuration." -ForegroundColor Yellow
    Write-Host "Required variables:" -ForegroundColor Yellow
    Write-Host "  DATABASE_URL=postgresql://user:password@localhost:5432/dbname" -ForegroundColor Gray
    Write-Host "  PYTHON_EXECUTABLE=C:\Path\To\python.exe (optional)" -ForegroundColor Gray
    exit 1
}

# Install dependencies if needed
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    npm install --legacy-peer-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
}

# Change to project root if needed
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
Set-Location $projectRoot

# Start job worker using full node path
Write-Host "Starting job worker..." -ForegroundColor Green
Write-Host "The worker will poll for jobs every 30 seconds" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

& $nodePath start-job-worker.js 