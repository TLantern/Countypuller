#!/usr/bin/env pwsh
# Install PM2 and set up CountyPuller Job Worker as a service

Write-Host "Setting up PM2 Service for CountyPuller Job Worker..." -ForegroundColor Green

# Check if npm is available
try {
    $npmVersion = npm --version
    Write-Host "✅ npm version: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ npm not found. Please install Node.js first." -ForegroundColor Red
    exit 1
}

# Install PM2 globally if not already installed
Write-Host "Installing PM2..." -ForegroundColor Cyan
try {
    npm install -g pm2
    Write-Host "✅ PM2 installed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install PM2: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Create PM2 ecosystem file
$ecosystemConfig = @{
    apps = @(
        @{
            name = "countypuller-job-worker"
            script = "start-job-worker.js"
            cwd = $PWD.Path
            instances = 1
            autorestart = $true
            watch = $false
            max_memory_restart = "1G"
            env = @{
                NODE_ENV = "production"
            }
            log_file = "job-worker-pm2.log"
            out_file = "job-worker-out.log"
            error_file = "job-worker-error.log"
            time = $true
            restart_delay = 5000
            max_restarts = 10
            min_uptime = "10s"
        }
    )
}

$ecosystemJson = $ecosystemConfig | ConvertTo-Json -Depth 10
$ecosystemJson | Out-File -FilePath "ecosystem.config.json" -Encoding UTF8

Write-Host "✅ PM2 ecosystem configuration created" -ForegroundColor Green

# Start the application with PM2
Write-Host "Starting job worker with PM2..." -ForegroundColor Cyan
try {
    pm2 start ecosystem.config.json
    Write-Host "✅ Job worker started with PM2" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to start with PM2: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Save PM2 process list
pm2 save

# Install PM2 startup service (Windows service)
Write-Host "Installing PM2 Windows service..." -ForegroundColor Cyan
try {
    pm2-installer
    Write-Host "✅ PM2 Windows service installed" -ForegroundColor Green
} catch {
    Write-Host "⚠️  PM2 service installation may require manual setup" -ForegroundColor Yellow
    Write-Host "Run: npm install -g pm2-windows-service" -ForegroundColor Gray
    Write-Host "Then: pm2-service-install" -ForegroundColor Gray
}

Write-Host ""
Write-Host "PM2 Management Commands:" -ForegroundColor Cyan
Write-Host "  pm2 status                    # View all processes" -ForegroundColor Gray
Write-Host "  pm2 restart countypuller-job-worker  # Restart job worker" -ForegroundColor Gray
Write-Host "  pm2 stop countypuller-job-worker     # Stop job worker" -ForegroundColor Gray
Write-Host "  pm2 delete countypuller-job-worker   # Remove job worker" -ForegroundColor Gray
Write-Host "  pm2 logs countypuller-job-worker     # View logs" -ForegroundColor Gray
Write-Host "  pm2 monit                     # Monitor dashboard" -ForegroundColor Gray
Write-Host ""
Write-Host "✅ PM2 setup completed!" -ForegroundColor Green 