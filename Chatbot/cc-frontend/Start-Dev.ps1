#!/usr/bin/env pwsh
# CountyPuller Development Server Script

Write-Host "Starting CountyPuller Development Server..." -ForegroundColor Green
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
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create a .env file with your configuration." -ForegroundColor Yellow
    Write-Host ""
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

# Generate Prisma client using full node path
if (Test-Path "node_modules\prisma\build\index.js") {
    Write-Host "Generating Prisma client..." -ForegroundColor Yellow
    & $nodePath ".\node_modules\prisma\build\index.js" generate
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to generate Prisma client" -ForegroundColor Yellow
    }
}

# Start development server using full node path
Write-Host "Starting Next.js development server..." -ForegroundColor Green
Write-Host "The app will be available at http://localhost:3000" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "node_modules\next\dist\bin\next") {
    & $nodePath ".\node_modules\next\dist\bin\next" dev
} else {
    Write-Host "ERROR: Next.js not found. Please run: npm install --legacy-peer-deps" -ForegroundColor Red
    exit 1
} 