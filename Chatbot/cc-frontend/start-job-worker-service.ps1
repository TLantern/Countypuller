#!/usr/bin/env pwsh
# CountyPuller Job Worker Service Script
# This script is designed to be run by Windows Task Scheduler

# Set working directory to script location
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Configuration
$jobWorkerScript = "start-job-worker.js"
$pidFile = "job-worker.pid"
$logFile = "job-worker.log"
$maxLogSize = 10MB

# Function to write timestamped log
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $logFile -Value $logEntry
    if ($Level -eq "ERROR") {
        Write-Host $logEntry -ForegroundColor Red
    } elseif ($Level -eq "WARN") {
        Write-Host $logEntry -ForegroundColor Yellow
    } else {
        Write-Host $logEntry -ForegroundColor Green
    }
}

# Function to rotate log file if it gets too large
function Rotate-LogFile {
    if (Test-Path $logFile) {
        $logFileInfo = Get-Item $logFile
        if ($logFileInfo.Length -gt $maxLogSize) {
            $backupName = "$logFile.$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
            Move-Item $logFile $backupName
            Write-Log "Log file rotated to $backupName"
        }
    }
}

# Function to check if job worker is running
function Test-JobWorkerRunning {
    if (-not (Test-Path $pidFile)) {
        return $false
    }
    
    try {
        $processId = Get-Content $pidFile -ErrorAction Stop
        $process = Get-Process -Id $processId -ErrorAction Stop
        
        # Check if it's actually our job worker process
        if ($process.ProcessName -eq "node" -and $process.CommandLine -like "*$jobWorkerScript*") {
            return $true
        }
    } catch {
        # PID file exists but process doesn't, clean up
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    
    return $false
}

# Function to start job worker
function Start-JobWorker {
    try {
        Write-Log "Starting CountyPuller Job Worker..."
        
        # Check Node.js availability
        $nodePath = "C:\Program Files\nodejs\node.exe"
        if (-not (Test-Path $nodePath)) {
            # Try to find node in PATH
            $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
            if ($nodeCommand) {
                $nodePath = $nodeCommand.Source
            } else {
                throw "Node.js not found. Please install Node.js."
            }
        }
        
        # Start the process
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $nodePath
        $processInfo.Arguments = $jobWorkerScript
        $processInfo.WorkingDirectory = $scriptDir
        $processInfo.UseShellExecute = $false
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.CreateNoWindow = $true
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        
        # Set up event handlers for output
        $process.EnableRaisingEvents = $true
        Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action {
            if ($Event.SourceEventArgs.Data) {
                Add-Content -Path "$using:logFile" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [STDOUT] $($Event.SourceEventArgs.Data)"
            }
        } | Out-Null
        
        Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action {
            if ($Event.SourceEventArgs.Data) {
                Add-Content -Path "$using:logFile" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [STDERR] $($Event.SourceEventArgs.Data)"
            }
        } | Out-Null
        
        $process.Start() | Out-Null
        $process.BeginOutputReadLine()
        $process.BeginErrorReadLine()
        
        # Save PID
        $process.Id | Out-File -FilePath $pidFile -Encoding ASCII
        
        Write-Log "Job Worker started with PID: $($process.Id)"
        return $true
        
    } catch {
        Write-Log "Failed to start Job Worker: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

# Main execution
Write-Log "CountyPuller Job Worker Service Check Starting..."

# Rotate log if needed
Rotate-LogFile

# Check if job worker is already running
if (Test-JobWorkerRunning) {
    Write-Log "Job Worker is already running"
    exit 0
}

# Start job worker if not running
Write-Log "Job Worker not running, attempting to start..."
if (Start-JobWorker) {
    Write-Log "Job Worker service check completed successfully"
    exit 0
} else {
    Write-Log "Failed to start Job Worker" "ERROR"
    exit 1
} 