#!/bin/bash

# CountyPuller Job Worker Stop Script
echo "Stopping CountyPuller Job Worker..."

# Change to the script directory
cd "$(dirname "$0")"

# Check if PID file exists
if [ -f job-worker.pid ]; then
    PID=$(cat job-worker.pid)
    
    # Check if process is running
    if kill -0 $PID 2>/dev/null; then
        echo "Stopping job worker with PID: $PID"
        kill $PID
        
        # Wait for process to stop
        sleep 2
        
        # Force kill if still running
        if kill -0 $PID 2>/dev/null; then
            echo "Force killing job worker..."
            kill -9 $PID
        fi
        
        echo "Job worker stopped successfully"
    else
        echo "Job worker is not running (PID $PID not found)"
    fi
    
    # Remove PID file
    rm job-worker.pid
else
    echo "No PID file found. Job worker may not be running."
fi

# Also kill any remaining node processes with job-worker
pkill -f "node.*job-worker" && echo "Killed any remaining job-worker processes" 