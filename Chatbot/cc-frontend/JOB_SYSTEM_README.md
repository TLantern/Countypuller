# Job-Based Scraping System

## Overview

This system resolves the deployment issue where Python scripts cannot be executed directly from Next.js API routes in hosted environments (like Vercel). Instead of running Python directly, the system uses a queue-based approach with background job processing.

## How It Works

1. **Job Creation**: When a user clicks "Pull Records", the API creates a job record in the database
2. **Background Processing**: A separate Node.js worker process polls for pending jobs and executes them
3. **Status Polling**: The frontend polls the API to check job status and updates the UI accordingly

## Architecture

### Database Schema

The `scraping_job` table stores job information:
- `id`: Unique job identifier  
- `job_type`: Type of job (e.g., "LIS_PENDENS_PULL")
- `status`: Current status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- `created_at`: When the job was created
- `completed_at`: When the job finished
- `parameters`: Job configuration (JSON)
- `result`: Job output (JSON)
- `error_message`: Error details if failed
- `records_processed`: Number of records processed

### API Endpoints

#### POST /api/pull-lph
Creates a new scraping job
```json
{
  "success": true,
  "job_id": "uuid-here",
  "status": "PENDING",
  "message": "Scraping job queued successfully"
}
```

#### GET /api/pull-lph?job_id=uuid
Checks job status
```json
{
  "success": true,
  "job_id": "uuid-here", 
  "status": "IN_PROGRESS",
  "created_at": "2024-01-01T12:00:00Z",
  "records_processed": 5
}
```

## Setup Instructions

### 1. Database Migration

The database schema has been updated. If you haven't run the migration yet:

```bash
cd cc-frontend
npx prisma migrate dev --name add_scraping_job_table
```

### 2. Running the Job Worker

The job worker is a separate Node.js process that must run alongside your web application:

```bash
# In the cc-frontend directory
npm run job-worker
```

For production, you should run this as a daemon/service:

#### Using PM2 (recommended):
```bash
npm install -g pm2
pm2 start "npm run job-worker" --name "scraping-worker"
pm2 save
pm2 startup
```

#### Using nohup (Linux/Mac):
```bash
nohup npm run job-worker > job-worker.log 2>&1 &
```

#### Windows Service:
Use a tool like `node-windows` or run in a separate terminal/PowerShell window.

### 3. Environment Variables

Ensure these environment variables are set:
- `DATABASE_URL`: PostgreSQL connection string
- `DB_URL`: Same as DATABASE_URL (used by Python script)
- Any other environment variables needed by the Python scraper

## Deployment Options

### Option 1: Separate Server/Container
- Deploy the web app to Vercel/Netlify
- Deploy the job worker to a separate server (AWS EC2, DigitalOcean, etc.)
- Both connect to the same database

### Option 2: Railway/Render 
- Deploy both web app and worker together on platforms that support background processes
- Use a `Procfile` to define both processes

### Option 3: Local Development
- Run the web app with `npm run dev`
- Run the job worker with `npm run job-worker` in a separate terminal

## Monitoring

### Checking Job Status
Jobs can be monitored through:
1. Database queries on the `scraping_job` table
2. The frontend job status display
3. Worker process logs

### Troubleshooting

1. **Jobs stuck in PENDING**: Worker process not running
2. **Jobs failing**: Check worker logs for Python execution errors
3. **Database connection issues**: Verify DATABASE_URL is correct

### Worker Logs
The job worker outputs detailed logs including:
- Job processing start/completion
- Python script output
- Error messages
- Database operations

## Frontend Integration

The dashboard automatically:
- Creates jobs when "Pull Records" is clicked
- Shows real-time status updates
- Displays job ID for tracking
- Refreshes data when jobs complete

## Future Enhancements

1. **Job Retry Logic**: Automatically retry failed jobs
2. **Job Queue Management**: Priority queues, rate limiting
3. **Multiple Workers**: Scale horizontally with multiple worker processes
4. **Job History**: UI for viewing completed job history
5. **Scheduled Jobs**: Cron-like scheduling for automated scraping
6. **Real-time Updates**: WebSocket/Server-Sent Events instead of polling

## Security Considerations

1. **Authentication**: Ensure only authorized users can create jobs
2. **Input Validation**: Validate job parameters to prevent injection
3. **Resource Limits**: Implement timeouts and resource constraints
4. **Logging**: Secure logging of sensitive data

## Python Script Requirements

The Python script should:
1. Accept command-line arguments (--limit, etc.)
2. Output progress information to stdout
3. Exit with code 0 on success, non-zero on failure
4. Handle database connections properly
5. Support running from different working directories 