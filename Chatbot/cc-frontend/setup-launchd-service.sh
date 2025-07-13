#!/bin/bash

# CountyPuller Job Worker launchd Service Setup
echo "Setting up CountyPuller Job Worker as a launchd service..."

# Change to the script directory
cd "$(dirname "$0")"

# Copy the plist file to the user's LaunchAgents directory
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="com.countypuller.jobworker.plist"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Copy the plist file
cp "$PLIST_FILE" "$LAUNCH_AGENTS_DIR/"

echo "✅ Copied $PLIST_FILE to $LAUNCH_AGENTS_DIR"

# Load the service
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_FILE"

echo "✅ Loaded the job worker service"

# Start the service
launchctl start com.countypuller.jobworker

echo "✅ Started the job worker service"

echo ""
echo "Service setup complete!"
echo "The job worker will now:"
echo "- Start automatically when you log in"
echo "- Restart automatically if it crashes"
echo "- Run continuously in the background"
echo ""
echo "To manage the service:"
echo "- Check status: launchctl list | grep countypuller"
echo "- Stop service: launchctl stop com.countypuller.jobworker"
echo "- Start service: launchctl start com.countypuller.jobworker"
echo "- Unload service: launchctl unload ~/Library/LaunchAgents/com.countypuller.jobworker.plist"
echo ""
echo "Logs will be written to:"
echo "- Output: job-worker.log"
echo "- Errors: job-worker-error.log" 