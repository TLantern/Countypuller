#!/usr/bin/env pwsh
# Manage CountyPuller Job Worker Windows Task

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("status", "start", "stop", "restart", "remove", "logs")]
    [string]$Action
)

$taskName = "CountyPuller-JobWorker"
$logFile = "job-worker.log"

function Show-Status {
    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
        
        Write-Host "Task Status:" -ForegroundColor Cyan
        Write-Host "  Name: $($task.TaskName)" -ForegroundColor Gray
        Write-Host "  State: $($task.State)" -ForegroundColor Gray
        Write-Host "  Last Run: $($taskInfo.LastRunTime)" -ForegroundColor Gray
        Write-Host "  Last Result: $($taskInfo.LastTaskResult)" -ForegroundColor Gray
        Write-Host "  Next Run: $($taskInfo.NextRunTime)" -ForegroundColor Gray
        
        # Check if job worker process is actually running
        if (Test-Path "job-worker.pid") {
            $processId = Get-Content "job-worker.pid" -ErrorAction SilentlyContinue
            if ($processId) {
                try {
                    $process = Get-Process -Id $processId -ErrorAction Stop
                    Write-Host "  Process: Running (PID: $processId)" -ForegroundColor Green
                } catch {
                    Write-Host "  Process: Not running (stale PID file)" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "  Process: No PID file found" -ForegroundColor Yellow
        }
        
    } catch {
        Write-Host "Task '$taskName' not found or error occurred: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Start-Task {
    try {
        Start-ScheduledTask -TaskName $taskName
        Write-Host "✅ Task '$taskName' started successfully" -ForegroundColor Green
    } catch {
        Write-Host "❌ Failed to start task: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Stop-Task {
    try {
        Stop-ScheduledTask -TaskName $taskName
        Write-Host "✅ Task '$taskName' stopped successfully" -ForegroundColor Green
        
        # Also kill any running job worker processes
        if (Test-Path "job-worker.pid") {
            $processId = Get-Content "job-worker.pid" -ErrorAction SilentlyContinue
            if ($processId) {
                try {
                    Stop-Process -Id $processId -Force -ErrorAction Stop
                    Write-Host "✅ Job worker process (PID: $processId) terminated" -ForegroundColor Green
                } catch {
                    Write-Host "⚠️  Could not terminate process PID: $processId" -ForegroundColor Yellow
                }
            }
            Remove-Item "job-worker.pid" -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "❌ Failed to stop task: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Restart-Task {
    Write-Host "Restarting task..." -ForegroundColor Cyan
    Stop-Task
    Start-Sleep -Seconds 2
    Start-Task
}

function Remove-Task {
    try {
        # Stop first
        Stop-Task
        Start-Sleep -Seconds 1
        
        # Remove the task
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "✅ Task '$taskName' removed successfully" -ForegroundColor Green
    } catch {
        Write-Host "❌ Failed to remove task: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Show-Logs {
    if (Test-Path $logFile) {
        Write-Host "Recent job worker logs:" -ForegroundColor Cyan
        Write-Host "=" * 50 -ForegroundColor Gray
        Get-Content $logFile -Tail 50
        Write-Host "=" * 50 -ForegroundColor Gray
        Write-Host "To monitor live: Get-Content '$logFile' -Wait" -ForegroundColor Yellow
    } else {
        Write-Host "Log file '$logFile' not found" -ForegroundColor Red
    }
}

# Execute the requested action
switch ($Action) {
    "status" { Show-Status }
    "start" { Start-Task }
    "stop" { Stop-Task }
    "restart" { Restart-Task }
    "remove" { Remove-Task }
    "logs" { Show-Logs }
} 