// Load environment variables from .env file
require('dotenv').config();

const { PrismaClient } = require('@prisma/client');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const prisma = new PrismaClient();

// Helper function to find Python executable
function findPythonExecutable() {
  // Check environment variables first
  if (process.env.PYTHON_EXECUTABLE) {
    console.log(`[DEBUG] Found PYTHON_EXECUTABLE: ${process.env.PYTHON_EXECUTABLE}`);
    // Remove any existing quotes and add them back properly
    let pythonPath = process.env.PYTHON_EXECUTABLE.replace(/^["']|["']$/g, '');
    return pythonPath;
  }
  
  if (process.env.PYTHON_PATH) {
    console.log(`[DEBUG] Found PYTHON_PATH: ${process.env.PYTHON_PATH}`);
    // Remove any existing quotes and add them back properly
    let pythonPath = process.env.PYTHON_PATH.replace(/^["']|["']$/g, '');
    return pythonPath;
  }
  
  // Common Python paths on Windows (prioritize working conda environment)
  const commonPaths = [
    'C:\\ProgramData\\miniconda3\\python.exe', // Your working conda base environment (PRIORITY)
    'c:\\Users\\tmbor\\Countypuller\\.conda\\python.exe', // Your project conda environment
    `${process.env.USERPROFILE}\\Countypuller\\.conda\\python.exe`, // Dynamic conda path
    'C:\\Users\\tmbor\\python.exe', // Your original path
    'C:\\Program Files\\Python311\\python.exe', // Your Python 3.11 installation (moved down due to permission issues)
    'C:\\Python39\\python.exe',
    'C:\\Python310\\python.exe',
    'C:\\Python311\\python.exe',
    'C:\\Python312\\python.exe',
    'C:\\Python313\\python.exe',
    `C:\\Users\\${process.env.USERNAME}\\AppData\\Local\\Programs\\Python\\Python39\\python.exe`,
    `C:\\Users\\${process.env.USERNAME}\\AppData\\Local\\Programs\\Python\\Python310\\python.exe`,
    `C:\\Users\\${process.env.USERNAME}\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`,
    `C:\\Users\\${process.env.USERNAME}\\AppData\\Local\\Programs\\Python\\Python312\\python.exe`,
    `C:\\Users\\${process.env.USERNAME}\\AppData\\Local\\Programs\\Python\\Python313\\python.exe`,
  ];
  
  console.log(`[DEBUG] Searching for Python in common paths...`);
  for (const pythonPath of commonPaths) {
    if (fs.existsSync(pythonPath)) {
      console.log(`[DEBUG] Found Python at: ${pythonPath}`);
      return pythonPath;
    }
  }
  
  console.log(`[DEBUG] No Python found in common paths, falling back to 'python' in PATH`);
  return 'python';
}

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
    
    // Use environment variable with fallbacks and auto-detection
    const pythonExecutable = findPythonExecutable();
    
    console.log(`[DEBUG] Using Python executable: ${pythonExecutable}`);
    console.log(`[DEBUG] Running: ${pythonExecutable} ${scriptPath} ${args.join(' ')} in ${scriptDir}`);
    console.log(`[DEBUG] DATABASE_URL available: ${process.env.DATABASE_URL ? 'YES' : 'NO'}`);
    console.log(`[DEBUG] Environment variables:`);
    console.log(`[DEBUG]   PYTHON_EXECUTABLE: ${process.env.PYTHON_EXECUTABLE || 'NOT SET'}`);
    console.log(`[DEBUG]   PYTHON_PATH: ${process.env.PYTHON_PATH || 'NOT SET'}`);
    console.log(`[DEBUG]   PATH: ${process.env.PATH ? 'SET (length: ' + process.env.PATH.length + ')' : 'NOT SET'}`);
    console.log(`[DEBUG] Working directory: ${scriptDir}`);
    console.log(`[DEBUG] Script exists: ${require('fs').existsSync(scriptPath)}`);
    
    // Check if python executable exists (if it's an absolute path)
    if (require('path').isAbsolute(pythonExecutable)) {
      console.log(`[DEBUG] Python executable exists: ${require('fs').existsSync(pythonExecutable)}`);
    } else {
      console.log(`[DEBUG] Python executable is relative/command: ${pythonExecutable}`);
    }
    
    const pythonProcess = spawn(pythonExecutable, [path.basename(scriptPath), ...args], {
      cwd: scriptDir,
      env: {
        ...process.env,
        DATABASE_URL: process.env.DATABASE_URL,
        NODE_ENV: process.env.NODE_ENV,
        PATH: process.env.PATH
      },
      windowsVerbatimArguments: false, // Handle spaces in paths correctly on Windows
      stdio: ['ignore', 'pipe', 'pipe']
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
      
      // Parse real-time progress updates for Agent Scrape jobs
      if (scriptPath.includes('agent_cli.py')) {
        const progressMatch = chunk.match(/PROGRESS:\s+(\d+)\/(\d+)\s+valid records/i);
        if (progressMatch) {
          const current = parseInt(progressMatch[1]);
          const target = parseInt(progressMatch[2]);
          const progressPercent = Math.min(100, (current / target) * 100);
          
          console.log(`[PROGRESS UPDATE] ${current}/${target} valid records (${progressPercent.toFixed(1)}%)`);
        }
      }
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
    if (job.job_type === 'MD_CASE_SEARCH') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/MdCaseSearch.py');
      const limit = job.parameters?.limit || 20;
      console.log(`[DEBUG] MD Case Search Job userId: ${job.userId}`);
      console.log(`[DEBUG] MD Case Search Job object:`, JSON.stringify(job, null, 2));
      const args = ['--limit', limit.toString(), '--user-id', job.userId, '--ensure-fresh', '--target-count', '20'];
      console.log(`[DEBUG] MD Case Search Arguments being passed:`, args);
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+fresh records/i) || 
                           result.output.match(/(\d+)\s+new unique records/i) ||
                           result.output.match(/(\d+)\s+total records/i) || 
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
      const limit = job.parameters?.limit || 20;
      console.log(`[DEBUG] Hillsborough NH Job userId: ${job.userId}`);
      console.log(`[DEBUG] Hillsborough NH Job object:`, JSON.stringify(job, null, 2));
      const args = ['--max-records', limit.toString(), '--user-id', job.userId, '--ensure-fresh', '--target-count', '20'];
      console.log(`[DEBUG] Hillsborough NH Arguments being passed:`, args);
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+fresh records/i) ||
                           result.output.match(/(\d+)\s+new unique records/i) ||
                           result.output.match(/(\d+)\s+new records/i) ||
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
      const limit = job.parameters?.limit || 20;
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
        '--to-date', toDateStr,
        '--ensure-fresh', '--target-count', '20'
      ];
      console.log(`[DEBUG] Brevard FL Arguments being passed:`, args);
      console.log(`[DEBUG] Date range: ${fromDateStr} to ${toDateStr} (${dateFilter} days back)`);
      
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output (adjust regex as needed based on actual output)
        const recordsMatch = result.output.match(/(\d+)\s+fresh records/i) ||
                           result.output.match(/(\d+)\s+new unique records/i) ||
                           result.output.match(/(\d+)\s+new records/i) ||
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
    } else if (job.job_type === 'FULTON_GA_PULL') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/FultonGA.py');
      const limit = job.parameters?.limit || 20;
      const dateFilter = job.parameters?.dateFilter || 7;
      console.log(`[DEBUG] Fulton GA Job userId: ${job.userId}`);
      console.log(`[DEBUG] Fulton GA Job object:`, JSON.stringify(job, null, 2));
      
      // Calculate date range from dateFilter (days back from today)
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(toDate.getDate() - dateFilter);
      
      // Format dates as MM/DD/YYYY for FultonGA.py
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
        '--to-date', toDateStr,
        '--ensure-fresh', '--target-count', '20'
      ];
      console.log(`[DEBUG] Fulton GA Arguments being passed:`, args);
      console.log(`[DEBUG] Date range: ${fromDateStr} to ${toDateStr} (${dateFilter} days back)`);
      
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output
        const recordsMatch = result.output.match(/(\d+)\s+fresh records/i) ||
                           result.output.match(/(\d+)\s+new unique records/i) ||
                           result.output.match(/(\d+)\s+new records/i) ||
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
        console.log(`[SUCCESS] Fulton GA Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else if (job.job_type === 'COBB_GA_PULL') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/PullingBots/CobbGA.py');
      const limit = job.parameters?.limit || 20;
      const dateFilter = job.parameters?.dateFilter || 7;
      console.log(`[DEBUG] Cobb GA Job userId: ${job.userId}`);
      console.log(`[DEBUG] Cobb GA Job object:`, JSON.stringify(job, null, 2));
      
      // Calculate date range from dateFilter (days back from today)
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(toDate.getDate() - dateFilter);
      
      // Format dates as MM/DD/YYYY for CobbGA.py
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
        '--to-date', toDateStr,
        '--ensure-fresh', '--target-count', '20'
      ];
      console.log(`[DEBUG] Cobb GA Arguments being passed:`, args);
      console.log(`[DEBUG] Date range: ${fromDateStr} to ${toDateStr} (${dateFilter} days back)`);
      
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Look for records processed in the output
        const recordsMatch = result.output.match(/(\d+)\s+fresh records/i) ||
                           result.output.match(/(\d+)\s+new unique records/i) ||
                           result.output.match(/(\d+)\s+new records/i) ||
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
        console.log(`[SUCCESS] Cobb GA Job ${job.id} completed successfully`);
      } else {
        throw new Error(result.error);
      }
    } else if (job.job_type === 'AGENT_SCRAPE') {
      const scriptPath = path.resolve(__dirname, '../../Chatbot/re-agent/agent_cli.py');
      const rawCounty = job.parameters?.county || 'harris';
      // Clean county name by removing parenthetical text like "(recommended)"
      const county = rawCounty.replace(/\s*\([^)]*\)\s*/g, '').trim();
      const filters = job.parameters?.filters || {};
      console.log(`[DEBUG] Agent Scrape Job userId: ${job.userId}`);
      console.log(`[DEBUG] Agent Scrape Job object:`, JSON.stringify(job, null, 2));
      
      // Convert filters to command line arguments
      const args = [
        '--county', county,
        '--user-id', job.userId
      ];
      
      // Add filter arguments if provided
      if (filters.dateFrom) {
        args.push('--date-from', filters.dateFrom);
      }
      if (filters.dateTo) {
        args.push('--date-to', filters.dateTo);
      }
      if (filters.documentType) {
        args.push('--document-type', filters.documentType);
      }
      if (filters.pageSize) {
        args.push('--page-size', filters.pageSize.toString());
      }
      
      // Add target count for fast debugging
      args.push('--target-count', '10');
      
      // Set smaller page size for faster debugging
      args.push('--page-size', '10');
      
      console.log(`[DEBUG] Agent Scrape Arguments being passed:`, args);
      
      const result = await runPython(scriptPath, args);
      if (result.success) {
        // Try to parse JSON result from output
        let parsedResult;
        try {
          // Look for JSON in the output (the CLI script outputs JSON)
          const jsonMatch = result.output.match(/\{.*\}/s);
          if (jsonMatch) {
            parsedResult = JSON.parse(jsonMatch[0]);
          }
        } catch (e) {
          console.log(`[DEBUG] Could not parse JSON from output: ${e.message}`);
        }
        
        // Extract records count from parsed result or output
        let recordsProcessed = null;
        if (parsedResult && parsedResult.metadata) {
          recordsProcessed = parsedResult.metadata.processed || parsedResult.metadata.total_found;
        } else {
          // Look for progress updates in logs - prioritize valid records found
          const progressMatch = result.output.match(/PROGRESS:\s+(\d+)\/(\d+)\s+valid records/i);
          if (progressMatch) {
            recordsProcessed = parseInt(progressMatch[1]); // Use valid records count
          } else {
            // Fallback to regex matching
            const recordsMatch = result.output.match(/(\d+)\s+records/i) ||
                               result.output.match(/processed\s+(\d+)\s+records/i) ||
                               result.output.match(/found\s+(\d+)\s+records/i);
            recordsProcessed = recordsMatch ? parseInt(recordsMatch[1]) : null;
          }
        }
        
        await prisma.scraping_job.update({
          where: { id: job.id },
          data: {
            status: JobStatus.COMPLETED,
            completed_at: new Date(),
            result: parsedResult || { output: result.output },
            records_processed: recordsProcessed
          }
        });
        console.log(`[SUCCESS] Agent Scrape Job ${job.id} completed successfully`);
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