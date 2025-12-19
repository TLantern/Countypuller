#!/bin/bash

# CountyPuller Job Worker Status Script
echo "Checking CountyPuller Job Worker status..."

# Change to the project root directory (parent of scripts/)
cd "$(dirname "$0")/../.."

# Check if PID file exists
if [ -f job-worker.pid ]; then
    PID=$(cat job-worker.pid)
    
    # Check if process is running
    if kill -0 $PID 2>/dev/null; then
        echo "✅ Job worker is running with PID: $PID"
        
        # Show recent logs
        echo ""
        echo "Recent logs (last 10 lines):"
        echo "================================"
        if [ -f job-worker.log ]; then
            tail -10 job-worker.log
        else
            echo "No log file found"
        fi
    else
        echo "❌ Job worker is not running (PID $PID not found)"
        rm job-worker.pid
    fi
else
    echo "❌ No PID file found. Job worker is not running."
fi

# Check for any running job-worker processes
echo ""
echo "All job-worker processes:"
echo "========================"
ps aux | grep -E "node.*job-worker" | grep -v grep || echo "No job-worker processes found" 