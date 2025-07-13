#!/bin/bash

# CountyPuller Job Worker Daemon Startup Script
echo "Starting CountyPuller Job Worker as daemon..."

# Change to the script directory
cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

# Start the job worker in the background with nohup
nohup node start-job-worker.js > job-worker.log 2>&1 &

# Get the process ID
PID=$!
echo $PID > job-worker.pid

echo "Job worker started with PID: $PID"
echo "Logs are being written to: job-worker.log"
echo "To stop the worker, run: kill $PID"
echo "Or use the stop script: ./stop-job-worker.sh" 