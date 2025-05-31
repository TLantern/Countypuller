const { PrismaClient } = require('../src/generated/prisma');
const { spawn } = require('child_process');
const path = require('path');

const prisma = new PrismaClient();

// Job status enum
const JobStatus = {
  PENDING: 'PENDING',
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED'
};

function runPython(scriptPath, args) {
  return new Promise((resolve) => {
    const scriptDir = path.dirname(scriptPath);
    const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
    console.log(`[DEBUG] Running: ${pythonExecutable} ${scriptPath} ${args.join(' ')} in ${scriptDir}`);
    const pythonProcess = spawn(pythonExecutable, [path.basename(scriptPath), ...args], {
      cwd: scriptDir,
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
  await prisma.scraping_job.update({
    where: { id: job.id },
    data: { status: JobStatus.IN_PROGRESS }
  });
  try {
    if (job.job_type === 'LIS_PENDENS_PULL') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/LpH.py');
      const limit = job.parameters?.limit || 10;
      const args = ['--limit', limit.toString()];
      const result = await runPython(scriptPath, args);
      if (result.success) {
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
    const pendingJobs = await prisma.scraping_job.findMany({
      where: { status: JobStatus.PENDING },
      orderBy: { created_at: 'asc' },
      take: 1
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
  setInterval(pollForJobs, 30000);
  await pollForJobs();
}

process.on('SIGINT', async () => {
  console.log('[INFO] Shutting down job worker...');
  await prisma.$disconnect();
  process.exit(0);
});

main().catch(console.error); 