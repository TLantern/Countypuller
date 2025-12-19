# Job Worker Daemon Setup

This guide explains how to run the CountyPuller job worker permanently in the background.

## Option 1: Simple Background Process (Recommended for Development)

### Start the job worker as a daemon:
```bash
./start-job-worker-daemon.sh
```

### Check the status:
```bash
./status-job-worker.sh
```

### Stop the job worker:
```bash
./stop-job-worker.sh
```

### Features:
- ✅ Runs in background
- ✅ Survives terminal closure
- ✅ Logs to `job-worker.log`
- ❌ Doesn't restart on crash
- ❌ Doesn't start on system boot

## Option 2: macOS System Service (Recommended for Production)

### Set up as a system service:
```bash
./setup-launchd-service.sh
```

### Manage the service:
```bash
# Check status
launchctl list | grep countypuller

# Stop service
launchctl stop com.countypuller.jobworker

# Start service
launchctl start com.countypuller.jobworker

# Remove service
launchctl unload ~/Library/LaunchAgents/com.countypuller.jobworker.plist
```

### Features:
- ✅ Runs in background
- ✅ Survives terminal closure
- ✅ Automatically restarts on crash
- ✅ Starts automatically on login
- ✅ Logs to `job-worker.log` and `job-worker-error.log`

## Option 3: Manual Background Process

### Start manually:
```bash
nohup node start-job-worker.js > job-worker.log 2>&1 &
```

### Stop manually:
```bash
pkill -f "node.*job-worker"
```

## Monitoring

### View logs in real-time:
```bash
tail -f job-worker.log
```

### Check for errors:
```bash
tail -f job-worker-error.log
```

### View recent activity:
```bash
./status-job-worker.sh
```

## Troubleshooting

### If the job worker won't start:
1. Check that all dependencies are installed: `npm install`
2. Verify environment variables are set in `.env`
3. Check database connection: `npx prisma db push`
4. Review logs for errors: `cat job-worker.log`

### If jobs aren't being processed:
1. Check database for pending jobs: `npx prisma studio`
2. Verify Python dependencies are installed
3. Check the job worker logs for errors

### Common issues:
- **Permission denied**: Make sure scripts are executable (`chmod +x *.sh`)
- **Node not found**: Update the path in `com.countypuller.jobworker.plist`
- **Database connection**: Verify `DATABASE_URL` in `.env` 