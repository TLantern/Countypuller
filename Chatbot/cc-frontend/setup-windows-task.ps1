#!/usr/bin/env pwsh
# Setup Windows Task Scheduler for CountyPuller Job Worker

Write-Host "Setting up Windows Task Scheduler for CountyPuller Job Worker..." -ForegroundColor Green

# Get current directory
$currentDir = Get-Location
$scriptPath = Join-Path $currentDir "start-job-worker-service.ps1"
$logPath = Join-Path $currentDir "job-worker.log"

# Task configuration
$taskName = "CountyPuller-JobWorker"
$taskDescription = "CountyPuller Job Worker - Processes background jobs for property data"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task '$taskName' already exists. Removing..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Create the action (what to run)
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptPath`""

# Create the trigger (when to run - at startup and every 5 minutes)
$triggerStartup = New-ScheduledTaskTrigger -AtStartup
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)

# Create the principal (run as SYSTEM with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create task settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Register the task
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($triggerStartup, $triggerRepeat) -Principal $principal -Settings $settings -Description $taskDescription
    Write-Host "✅ Task '$taskName' created successfully!" -ForegroundColor Green
    
    # Start the task immediately
    Start-ScheduledTask -TaskName $taskName
    Write-Host "✅ Task started!" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Task Management Commands:" -ForegroundColor Cyan
    Write-Host "  View status: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
    Write-Host "  Start task:  Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
    Write-Host "  Stop task:   Stop-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
    Write-Host "  Remove task: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Logs location: $logPath" -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ Failed to create task: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} 