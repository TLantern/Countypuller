const { PrismaClient } = require('@prisma/client');
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
      console.log(`[DEBUG] Job userId: ${job.userId}`);
      console.log(`[DEBUG] Job object:`, JSON.stringify(job, null, 2));
      const args = ['--limit', limit.toString(), '--user-id', job.userId];
      console.log(`[DEBUG] Arguments being passed:`, args);
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
    } else if (job.job_type === 'MD_CASE_SEARCH') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/MdCaseSearch.py');
      const limit = job.parameters?.limit || 10;
      console.log(`[DEBUG] MD Case Search Job userId: ${job.userId}`);
      console.log(`[DEBUG] MD Case Search Job object:`, JSON.stringify(job, null, 2));
      const args = ['--limit', limit.toString(), '--user-id', job.userId];
      console.log(`[DEBUG] MD Case Search Arguments being passed:`, args);
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+total records/i) || 
                           result.output.match(/(\d+)\s+records/i) ||
                           result.output.match(/(\d+)\s+unique records/i);
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
        console.log(`[SUCCESS] MD Case Search Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else if (job.job_type === 'HILLSBOROUGH_NH_PULL') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/HillsboroughNH.py');
      const limit = job.parameters?.limit || 10;
      console.log(`[DEBUG] Hillsborough NH Job userId: ${job.userId}`);
      console.log(`[DEBUG] Hillsborough NH Job object:`, JSON.stringify(job, null, 2));
      const args = ['--max-records', limit.toString(), '--user-id', job.userId];
      console.log(`[DEBUG] Hillsborough NH Arguments being passed:`, args);
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+new records/i) ||
                           result.output.match(/(\d+)\s+records/i) ||
                           result.output.match(/Found\s+(\d+)\s+records/i);
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
        console.log(`[SUCCESS] Hillsborough NH Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else if (job.job_type === 'BREVARD_FL_PULL') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/BrevardFL.py');
      const limit = job.parameters?.limit || 10;
      const dateFilter = job.parameters?.dateFilter || 7;
      console.log(`[DEBUG] Brevard FL Job userId: ${job.userId}`);
      console.log(`[DEBUG] Brevard FL Job object:`, JSON.stringify(job, null, 2));
      
      // Calculate date range from dateFilter (days back from today)
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(toDate.getDate() - dateFilter);
      
      // Format dates as MM/DD/YYYY for BrevardFL.py
      const formatDate = (date) => {
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const year = date.getFullYear();
        return `${month}/${day}/${year}`;
      };
      
      const fromDateStr = formatDate(fromDate);
      const toDateStr = formatDate(toDate);
      
      const args = [
        '--max-records', limit.toString(), 
        '--user-id', job.userId,
        '--from-date', fromDateStr,
        '--to-date', toDateStr
      ];
      console.log(`[DEBUG] Brevard FL Arguments being passed:`, args);
      console.log(`[DEBUG] Date range: ${fromDateStr} to ${toDateStr} (${dateFilter} days back)`);
      
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+new records/i) ||
                           result.output.match(/(\d+)\s+records/i) ||
                           result.output.match(/Found\s+(\d+)\s+records/i) ||
                           result.output.match(/Successfully processed\s+(\d+)\s+new records/i);
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
        console.log(`[SUCCESS] Brevard FL Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else if (job.job_type === 'TEST_SCRAPE') {
      // Test job type for system testing - just marks as completed
      console.log(`[DEBUG] Test scrape job - simulating completion`);
      await prisma.scraping_job.update({
        where: { id: job.id },
        data: {
          status: JobStatus.COMPLETED,
          completed_at: new Date(),
          result: { output: 'Test job completed successfully' },
          records_processed: 0
        }
      });
      console.log(`[SUCCESS] Test job ${job.id} completed successfully`);
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