const { PrismaClient } = require('../src/generated/prisma');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const prisma = new PrismaClient();

// Job status enum
const JobStatus = {
  PENDING: 'PENDING',
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED'
};

function runPython(scriptPath, args, pythonPath) {
  return new Promise((resolve) => {
    console.log(`[DEBUG] Running Python script: ${scriptPath}`);
    console.log(`[DEBUG] Python path: ${pythonPath}`);
    console.log(`[DEBUG] Arguments: ${args.join(' ')}`);
    
    const pythonProcess = spawn(pythonPath, [scriptPath, ...args], {
      cwd: path.dirname(scriptPath),
      env: process.env,
    });
    
    let output = '';
    let errorOutput = '';
    
    pythonProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      console.log(`[STDOUT] ${chunk}`);
      output += chunk;
    });
    
    pythonProcess.stderr.on('data', (data) => {
      const chunk = data.toString();
      console.log(`[STDERR] ${chunk}`);
      errorOutput += chunk;
    });
    
    pythonProcess.on('close', (code) => {
      console.log(`[DEBUG] Python process closed with code: ${code}`);
      if (code === 0) {
        resolve({ success: true, output });
      } else {
        resolve({ success: false, error: errorOutput || `Process exited with code ${code}` });
      }
    });
    
    pythonProcess.on('error', (err) => {
      console.log(`[ERROR] Python process error: ${err.message}`);
      resolve({ success: false, error: err.message });
    });
  });
}

async function processJob(job) {
  console.log(`[INFO] Processing job ${job.id} of type ${job.job_type}`);
  
  // Update job status to IN_PROGRESS
  await prisma.scraping_job.update({
    where: { id: job.id },
    data: { 
      status: JobStatus.IN_PROGRESS,
    }
  });

  try {
    if (job.job_type === 'LIS_PENDENS_PULL') {
      // Determine paths
      const isWindows = process.platform === 'win32';
      const scriptPath = path.resolve(process.cwd(), '../Chatbot/PullingBots/LpH.py');
      const limit = job.parameters?.limit || 10;
      const args = ['--limit', limit.toString()];
      
      console.log(`[DEBUG] Script path: ${scriptPath}`);
      console.log(`[DEBUG] Script exists: ${fs.existsSync(scriptPath)}`);
      
      // Determine Python executable path
      const pythonExecutable = isWindows ? 'python.exe' : 'python3';
      const venvPath = isWindows 
        ? path.resolve(process.cwd(), '../Chatbot/venv/Scripts', pythonExecutable)
        : path.resolve(process.cwd(), '../Chatbot/venv/bin', pythonExecutable);
      
      console.log(`[DEBUG] Python venv path: ${venvPath}`);
      console.log(`[DEBUG] Python executable exists: ${fs.existsSync(venvPath)}`);
      
      // Try virtual environment Python first
      let result = await runPython(scriptPath, args, venvPath);
      
      if (!result.success) {
        console.log(`[DEBUG] Virtual environment attempt failed, trying system Python`);
        // Fallback to system Python
        const systemPython = isWindows ? 'python' : 'python3';
        result = await runPython(scriptPath, args, systemPython);
      }
      
      if (result.success) {
        // Parse output to get record count if possible
        const recordsMatch = result.output.match(/(\d+)\s+new records/i);
        const recordsProcessed = recordsMatch ? parseInt(recordsMatch[1]) : null;
        
        await prisma.scraping_job.update({
          where: { id: job.id },
          data: { 
            status: JobStatus.COMPLETED,
            completed_at: new Date(),
            result: { output: result.output },
            records_processed: recordsProcessed
          }
        });
        
        console.log(`[SUCCESS] Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else {
      throw new Error(`Unknown job type: ${job.job_type}`);
    }
  } catch (error) {
    console.error(`[ERROR] Job ${job.id} failed:`, error);
    
    await prisma.scraping_job.update({
      where: { id: job.id },
      data: { 
        status: JobStatus.FAILED,
        completed_at: new Date(),
        error_message: error.message
      }
    });
  }
}

async function pollForJobs() {
  try {
    // Get pending jobs
    const pendingJobs = await prisma.scraping_job.findMany({
      where: { status: JobStatus.PENDING },
      orderBy: { created_at: 'asc' },
      take: 1 // Process one job at a time
    });

    if (pendingJobs.length > 0) {
      for (const job of pendingJobs) {
        await processJob(job);
      }
    } else {
      console.log('[INFO] No pending jobs found');
    }
  } catch (error) {
    console.error('[ERROR] Error polling for jobs:', error);
  }
}

async function main() {
  console.log('[INFO] Starting job worker...');
  
  // Poll for jobs every 30 seconds
  setInterval(pollForJobs, 30000);
  
  // Run immediately on startup
  await pollForJobs();
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('[INFO] Shutting down job worker...');
  await prisma.$disconnect();
  process.exit(0);
});

main().catch(console.error); 