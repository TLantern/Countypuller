#!/usr/bin/env pwsh
# Test CountyPuller Job Worker Setup

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "CountyPuller Job Worker Setup Test" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Test 1: Check Node.js installation
Write-Host "`n[Test 1] Node.js Installation" -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "[PASS] Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Node.js not found in PATH" -ForegroundColor Red
}

# Test 2: Check if .env file exists
Write-Host "`n[Test 2] Environment Configuration" -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "[PASS] .env file found" -ForegroundColor Green
    
    # Check for required environment variables
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "DATABASE_URL") {
        Write-Host "[PASS] DATABASE_URL configured" -ForegroundColor Green
    } else {
        Write-Host "[WARN] DATABASE_URL not found in .env" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] .env file not found" -ForegroundColor Red
}

# Test 3: Check npm dependencies
Write-Host "`n[Test 3] Dependencies" -ForegroundColor Yellow
if (Test-Path "node_modules") {
    Write-Host "[PASS] node_modules folder exists" -ForegroundColor Green
} else {
    Write-Host "[WARN] node_modules not found - run 'npm install'" -ForegroundColor Yellow
}

if (Test-Path "package.json") {
    Write-Host "[PASS] package.json found" -ForegroundColor Green
} else {
    Write-Host "[FAIL] package.json not found" -ForegroundColor Red
}

# Test 4: Check job worker script
Write-Host "`n[Test 4] Job Worker Script" -ForegroundColor Yellow
# Get project root (parent of scripts/management)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$jobWorkerPath = Join-Path $projectRoot "start-job-worker.js"

if (Test-Path $jobWorkerPath) {
    Write-Host "[PASS] start-job-worker.js found" -ForegroundColor Green
} else {
    Write-Host "[FAIL] start-job-worker.js not found at $jobWorkerPath" -ForegroundColor Red
}

if (Test-Path "scripts/job-worker.js") {
    Write-Host "[PASS] scripts/job-worker.js found" -ForegroundColor Green
} else {
    Write-Host "[FAIL] scripts/job-worker.js not found" -ForegroundColor Red
}

# Test 5: Check Windows Task Scheduler setup
Write-Host "`n[Test 5] Windows Task Scheduler" -ForegroundColor Yellow
$taskName = "CountyPuller-JobWorker"
try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    Write-Host "[PASS] Windows Task '$taskName' exists" -ForegroundColor Green
    Write-Host "   State: $($task.State)" -ForegroundColor Gray
    
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
    if ($taskInfo) {
        Write-Host "   Last Run: $($taskInfo.LastRunTime)" -ForegroundColor Gray
        Write-Host "   Last Result: $($taskInfo.LastTaskResult)" -ForegroundColor Gray
    }
} catch {
    Write-Host "[FAIL] Windows Task '$taskName' not found" -ForegroundColor Red
    Write-Host "   Run: .\setup-windows-task.ps1" -ForegroundColor Gray
}

# Test 6: Check for running processes
Write-Host "`n[Test 6] Running Processes" -ForegroundColor Yellow
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*job-worker*"}
if ($nodeProcesses) {
    Write-Host "[PASS] Job worker process(es) found:" -ForegroundColor Green
    foreach ($proc in $nodeProcesses) {
        Write-Host "   PID: $($proc.Id), CPU: $($proc.CPU), Memory: $([math]::Round($proc.WorkingSet64/1MB, 2)) MB" -ForegroundColor Gray
    }
} else {
    Write-Host "[WARN] No job worker processes currently running" -ForegroundColor Yellow
}

# Test 7: Check PID file
Write-Host "`n[Test 7] PID File" -ForegroundColor Yellow
if (Test-Path "job-worker.pid") {
    $pidContent = Get-Content "job-worker.pid" -ErrorAction SilentlyContinue
    if ($pidContent) {
        try {
            $process = Get-Process -Id $pidContent -ErrorAction Stop
            Write-Host "[PASS] PID file valid, process running (PID: $pidContent)" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] PID file exists but process not running (stale PID: $pidContent)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARN] PID file empty" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] No PID file (normal if using Task Scheduler)" -ForegroundColor Cyan
}

# Test 8: Check log files
Write-Host "`n[Test 8] Log Files" -ForegroundColor Yellow
if (Test-Path "job-worker.log") {
    $logSize = (Get-Item "job-worker.log").Length
    $logSizeMB = [math]::Round($logSize/1MB, 2)
    Write-Host "[PASS] job-worker.log exists ($logSizeMB MB)" -ForegroundColor Green
    
    # Check last few lines
    $lastLines = Get-Content "job-worker.log" -Tail 3 -ErrorAction SilentlyContinue
    if ($lastLines) {
        Write-Host "   Recent log entries:" -ForegroundColor Gray
        foreach ($line in $lastLines) {
            Write-Host "   $line" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "[INFO] No log file yet (will be created when job worker runs)" -ForegroundColor Cyan
}

# Test 9: Database connectivity (basic)
Write-Host "`n[Test 9] Database Connectivity" -ForegroundColor Yellow
try {
    # Check if we can run a basic Prisma command
    $prismaVersion = npx prisma --version 2>$null
    if ($prismaVersion) {
        Write-Host "[PASS] Prisma CLI available" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARN] Could not verify Prisma CLI" -ForegroundColor Yellow
}

# Test 10: Python environment
Write-Host "`n[Test 10] Python Environment" -ForegroundColor Yellow
try {
    if ($env:PYTHON_EXECUTABLE) {
        Write-Host "[PASS] PYTHON_EXECUTABLE set: $($env:PYTHON_EXECUTABLE)" -ForegroundColor Green
    } else {
        Write-Host "[INFO] PYTHON_EXECUTABLE not set (will auto-detect)" -ForegroundColor Cyan
    }
    
    # Try to find Python
    $pythonPaths = @(
        "C:\Program Files\Python311\python.exe",
        "c:\Users\tmbor\Countypuller\.conda\python.exe"
    )
    
    foreach ($path in $pythonPaths) {
        if (Test-Path $path) {
            Write-Host "[PASS] Python found at: $path" -ForegroundColor Green
            break
        }
    }
} catch {
    Write-Host "[WARN] Could not verify Python installation" -ForegroundColor Yellow
}

# Summary and recommendations
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "SUMMARY & RECOMMENDATIONS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`nNext Steps:" -ForegroundColor Yellow

# Check if Windows Task is set up
try {
    Get-ScheduledTask -TaskName $taskName -ErrorAction Stop | Out-Null
    Write-Host "[PASS] Windows Task Scheduler is configured" -ForegroundColor Green
    Write-Host "   Your job worker should start automatically" -ForegroundColor Gray
    Write-Host "   Monitor with: .\manage-job-worker-task.ps1 status" -ForegroundColor Gray
} catch {
    Write-Host "[TODO] Set up Windows Task Scheduler:" -ForegroundColor Yellow
    Write-Host "   .\setup-windows-task.ps1" -ForegroundColor Cyan
}

Write-Host "`nMonitoring Commands:" -ForegroundColor Yellow
Write-Host "   .\manage-job-worker-task.ps1 status    # Check status" -ForegroundColor Gray
Write-Host "   .\manage-job-worker-task.ps1 logs      # View logs" -ForegroundColor Gray
Write-Host "   Get-Content job-worker.log -Wait       # Monitor live" -ForegroundColor Gray

Write-Host "`nAlternative Setup (PM2):" -ForegroundColor Yellow
Write-Host "   .\install-pm2-service.ps1              # Install PM2" -ForegroundColor Gray
Write-Host "   pm2 status                             # Check PM2 status" -ForegroundColor Gray

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Test completed!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan 