import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

function runPython(scriptPath: string, args: string[], pythonPath: string) {
  return new Promise<{ success: boolean; output?: string; error?: string }>((resolve) => {
    console.log(`[DEBUG] Attempting to run Python with:`);
    console.log(`[DEBUG] Python path: ${pythonPath}`);
    console.log(`[DEBUG] Script path: ${scriptPath}`);
    console.log(`[DEBUG] Working directory: ${path.dirname(scriptPath)}`);
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

export async function POST(req: NextRequest) {
  // Check if we're in a deployed environment
  const isDeployed = process.cwd().includes('/var/task') || process.env.VERCEL || process.env.NODE_ENV === 'production';
  
  if (isDeployed) {
    console.log(`[DEBUG] Detected deployed environment, Python execution not supported`);
    return NextResponse.json({ 
      success: false, 
      error: 'Python execution is not supported in the deployed environment. Please run this locally.' 
    }, { status: 400 });
  }

  // Fix path resolution to avoid double "Chatbot"
  const isWindows = process.platform === 'win32';
  const scriptPath = path.resolve(process.cwd(), '../Chatbot/PullingBots/LpH.py');
  const args = ['--limit', '10'];
  
  console.log(`[DEBUG] Current working directory: ${process.cwd()}`);
  console.log(`[DEBUG] Platform: ${process.platform}`);
  console.log(`[DEBUG] Resolved script path: ${scriptPath}`);
  console.log(`[DEBUG] Script exists: ${fs.existsSync(scriptPath)}`);
  
  // Determine Python executable path based on platform
  const pythonExecutable = isWindows ? 'python.exe' : 'python3';
  const venvPath = isWindows 
    ? path.resolve(process.cwd(), '../Chatbot/venv/Scripts', pythonExecutable)
    : path.resolve(process.cwd(), '../Chatbot/venv/bin', pythonExecutable);
  
  console.log(`[DEBUG] Virtual environment Python path: ${venvPath}`);
  console.log(`[DEBUG] Python executable exists: ${fs.existsSync(venvPath)}`);
  
  // Try virtual environment Python first
  let result = await runPython(scriptPath, args, venvPath);
  
  if (!result.success) {
    console.log(`[DEBUG] Virtual environment attempt failed, trying system Python`);
    // Fallback to system Python
    const systemPython = isWindows ? 'python' : 'python3';
    result = await runPython(scriptPath, args, systemPython);
  }
  
  console.log(`[DEBUG] Final result:`, result);
  
  if (result.success) {
    return NextResponse.json({ success: true, output: result.output });
  } else {
    return NextResponse.json({ success: false, error: result.error || 'Unknown error' }, { status: 500 });
  }
}

export async function GET() {
  return NextResponse.json({ error: 'Method not allowed' }, { status: 405 });
} 