# Windows Stable Cron Job Setup for CountyPuller Job Worker

This guide provides multiple options for running the CountyPuller job worker as a stable, persistent service on Windows.

## 🏆 Option 1: Windows Task Scheduler (Recommended)

**Best for: Production environments, maximum stability, built-in Windows solution**

### Features:
- ✅ Native Windows integration
- ✅ Runs at system startup
- ✅ Automatic restart on failure
- ✅ Runs every 5 minutes to ensure process is alive
- ✅ Administrator privileges support
- ✅ Detailed logging and monitoring
- ✅ No additional dependencies

### Setup Instructions:

1. **Run the setup script** (requires Administrator privileges):
   ```powershell
   .\setup-windows-task.ps1
   ```

2. **Verify the task was created**:
   ```powershell
   .\manage-job-worker-task.ps1 status
   ```

### Management Commands:
```powershell
# Check status
.\manage-job-worker-task.ps1 status

# Start the task
.\manage-job-worker-task.ps1 start

# Stop the task
.\manage-job-worker-task.ps1 stop

# Restart the task
.\manage-job-worker-task.ps1 restart

# View recent logs
.\manage-job-worker-task.ps1 logs

# Remove the task
.\manage-job-worker-task.ps1 remove
```

### Task Configuration:
- **Trigger**: At system startup + every 5 minutes
- **User**: SYSTEM (runs with highest privileges)
- **Restart Policy**: 3 attempts with 1-minute intervals
- **Logging**: Comprehensive logging to `job-worker.log`

---

## 🚀 Option 2: PM2 Process Manager

**Best for: Development environments, advanced monitoring, clustering capabilities**

### Features:
- ✅ Advanced process monitoring
- ✅ Built-in clustering
- ✅ Web dashboard
- ✅ Real-time logs
- ✅ Memory usage monitoring
- ✅ Automatic restart on crash
- ✅ Hot reloads

### Setup Instructions:

1. **Install PM2 and set up service**:
   ```powershell
   .\install-pm2-service.ps1
   ```

2. **Verify PM2 is running**:
   ```powershell
   pm2 status
   ```

### Management Commands:
```powershell
# View all processes
pm2 status

# View live logs
pm2 logs countypuller-job-worker

# Restart the job worker
pm2 restart countypuller-job-worker

# Stop the job worker
pm2 stop countypuller-job-worker

# Remove the job worker
pm2 delete countypuller-job-worker

# Monitor dashboard
pm2 monit

# View detailed process info
pm2 describe countypuller-job-worker
```

---

## 🔧 Option 3: NSSM (Non-Sucking Service Manager)

**Best for: Custom Windows service setup, maximum control**

### Setup Instructions:

1. **Download NSSM** from https://nssm.cc/download

2. **Install the service**:
   ```powershell
   # Extract NSSM and add to PATH, then:
   nssm install CountyPullerJobWorker "C:\Program Files\nodejs\node.exe" "start-job-worker.js"
   nssm set CountyPullerJobWorker AppDirectory "C:\Users\tmbor\Countypuller\Chatbot\cc-frontend"
   nssm set CountyPullerJobWorker AppStdout "C:\Users\tmbor\Countypuller\Chatbot\cc-frontend\job-worker.log"
   nssm set CountyPullerJobWorker AppStderr "C:\Users\tmbor\Countypuller\Chatbot\cc-frontend\job-worker-error.log"
   nssm start CountyPullerJobWorker
   ```

3. **Manage the service**:
   ```powershell
   # Start service
   nssm start CountyPullerJobWorker
   
   # Stop service
   nssm stop CountyPullerJobWorker
   
   # Remove service
   nssm remove CountyPullerJobWorker
   ```

---

## 📊 Monitoring and Troubleshooting

### Log Files:
- **Main log**: `job-worker.log` - All job worker activity
- **Error log**: `job-worker-error.log` - Error messages only
- **PM2 logs**: `job-worker-pm2.log` - PM2-specific logs

### Monitoring Commands:
```powershell
# Watch logs in real-time
Get-Content job-worker.log -Wait

# Check Windows Task Scheduler logs
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" | Where-Object {$_.Message -like "*CountyPuller*"}

# Check system processes
Get-Process node

# Check listening ports (if applicable)
netstat -an | findstr :3000
```

### Common Issues:

1. **Task won't start**:
   - Check if Node.js path is correct
   - Verify `.env` file exists
   - Check database connectivity
   - Review logs for specific errors

2. **Process keeps crashing**:
   - Check memory usage
   - Review error logs
   - Verify all dependencies are installed
   - Check Python environment setup

3. **Jobs not processing**:
   - Verify database connection
   - Check job queue in database
   - Review Python script dependencies
   - Check file system permissions

## 🎯 Recommended Setup

For most production environments, use **Option 1 (Windows Task Scheduler)** because:

1. **Native Integration**: Built into Windows, no external dependencies
2. **Reliability**: Windows Task Scheduler is extremely stable
3. **Security**: Runs with appropriate system privileges
4. **Monitoring**: Easy to monitor through Windows Event Viewer
5. **Maintenance**: Standard Windows administration tools

### Quick Start (Recommended):

```powershell
# 1. Navigate to the project directory
cd "C:\Users\tmbor\Countypuller\Chatbot\cc-frontend"

# 2. Set up Windows Task Scheduler (run as Administrator)
.\setup-windows-task.ps1

# 3. Verify it's working
.\manage-job-worker-task.ps1 status

# 4. Monitor logs
.\manage-job-worker-task.ps1 logs
```

That's it! Your job worker will now run automatically at startup and check every 5 minutes to ensure it stays running.

---

## 🔄 Migration from Existing Setup

If you're currently using the manual daemon scripts, you can migrate:

1. **Stop existing processes**:
   ```powershell
   .\stop-job-worker.sh  # or equivalent Windows script
   ```

2. **Set up new service** (choose one option above)

3. **Verify the new service is working**

4. **Remove old startup scripts** from your manual startup procedures

## 📈 Performance Monitoring

Consider setting up additional monitoring:

1. **Windows Performance Monitor** for resource usage
2. **Database monitoring** for job queue depth
3. **Log rotation** to prevent disk space issues
4. **Health check endpoints** in your application

This setup ensures your CountyPuller job worker runs reliably 24/7 on Windows! 