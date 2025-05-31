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
  const scriptPath = path.resolve(process.cwd(), '../Chatbot/PullingBots/LpH.py');
  const args = ['--limit', '10'];
  
  console.log(`[DEBUG] Current working directory: ${process.cwd()}`);
  console.log(`[DEBUG] Resolved script path: ${scriptPath}`);
  console.log(`[DEBUG] Script exists: ${fs.existsSync(scriptPath)}`);
  
  const pythonPath = 'C:\\Users\\tmbor\\AppData\\Local\\Programs\\Python\\Python311\\python.exe';
  console.log(`[DEBUG] Python executable exists: ${fs.existsSync(pythonPath)}`);
  
  // Use your specific Python path first
  let result = await runPython(scriptPath, args, pythonPath);
  if (!result.success) {
    console.log(`[DEBUG] First attempt failed, trying fallback 'python'`);
    // Fallback to 'python' in PATH
    result = await runPython(scriptPath, args, 'python');
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