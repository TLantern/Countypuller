import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import csv from 'csv-parser';
import { createReadStream } from 'fs';

interface SkipTraceResult {
  raw_address: string;
  canonical_address: string;
  attomid: string | null;
  est_balance: number | null;
  available_equity: number | null;
  ltv: number | null;
  loans_count: number;
  processed_at: string;
}

interface SkipTraceResponse {
  success: boolean;
  data?: SkipTraceResult;
  error?: string;
  message?: string;
}

export async function POST(req: NextRequest): Promise<NextResponse<SkipTraceResponse>> {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ 
        success: false, 
        error: 'Not authenticated' 
      }, { status: 401 });
    }

    const body = await req.json();
    const { address } = body;

    if (!address || typeof address !== 'string' || !address.trim()) {
      return NextResponse.json({ 
        success: false, 
        error: 'Address is required and must be a non-empty string' 
      }, { status: 400 });
    }

    console.log(`🔍 Skip trace requested by user ${userId} for address: ${address}`);

    // Check if required environment variables are set
    const googleMapsApiKey = process.env.GOOGLE_MAPS_API_KEY;
    const uspsUserId = process.env.USPS_USER_ID; // Optional fallback
    const attomApiKey = process.env.ATTOM_API_KEY;

    console.log('Environment check:', {
      googleMapsApiKey: googleMapsApiKey ? 'SET' : 'MISSING',
      uspsUserId: uspsUserId ? 'SET' : 'MISSING',
      attomApiKey: attomApiKey ? 'SET' : 'MISSING'
    });

    if (!attomApiKey) {
      console.error('Missing required ATTOM_API_KEY environment variable');
      return NextResponse.json({ 
        success: false, 
        error: 'Skip trace requires ATTOM_API_KEY. Please set this environment variable and restart the server.' 
      }, { status: 500 });
    }

    if (!googleMapsApiKey && !uspsUserId) {
      console.error('Missing address validation API key: need either GOOGLE_MAPS_API_KEY or USPS_USER_ID');
      return NextResponse.json({ 
        success: false, 
        error: 'Skip trace requires either GOOGLE_MAPS_API_KEY or USPS_USER_ID for address validation. Please set one of these environment variables and restart the server.' 
      }, { status: 500 });
    }

    // Create temporary files for the pipeline
    const scriptsDir = path.join(process.cwd(), 'scripts');
    const tempDir = path.join(scriptsDir, 'temp');
    const timestamp = Date.now();
    const inputFile = path.join(tempDir, `skip_trace_input_${userId}_${timestamp}.csv`);
    const outputFile = path.join(tempDir, `skip_trace_output_${userId}_${timestamp}.csv`);

    try {
      // Ensure temp directory exists
      await fs.mkdir(tempDir, { recursive: true });

      // Create input CSV file with the single address
      const inputCsv = `address\n"${address.replace(/"/g, '""')}"`;
      await fs.writeFile(inputFile, inputCsv);

      console.log(`📝 Created input file: ${inputFile}`);

      // Run the address enrichment pipeline
      const pipelineScript = path.join(scriptsDir, 'address_enrichment_pipeline.py');
      
      const result = await runPipeline(pipelineScript, inputFile, outputFile);

      if (!result.success) {
        throw new Error(result.error || 'Pipeline execution failed');
      }

      // Check if output file exists before trying to read it
      try {
        await fs.access(outputFile);
      } catch (error) {
        throw new Error('Pipeline completed but no output file was created. Check API keys and pipeline logs.');
      }

      // Read the output CSV file
      const enrichedData = await readEnrichedData(outputFile);

      if (!enrichedData) {
        throw new Error('No data returned from address enrichment pipeline');
      }

      console.log(`✅ Skip trace completed for ${address}:`, {
        canonical_address: enrichedData.canonical_address,
        attomid: enrichedData.attomid,
        est_balance: enrichedData.est_balance,
        available_equity: enrichedData.available_equity,
        ltv: enrichedData.ltv
      });

      return NextResponse.json({
        success: true,
        data: enrichedData,
        message: 'Skip trace completed successfully'
      });

    } finally {
      // Clean up temporary files
      try {
        await fs.unlink(inputFile).catch(() => {});
        await fs.unlink(outputFile).catch(() => {});
      } catch (cleanupError) {
        console.warn('Failed to clean up temporary files:', cleanupError);
      }
    }

  } catch (error) {
    console.error('Skip trace error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'An unexpected error occurred'
    }, { status: 500 });
  }
}

async function runPipeline(scriptPath: string, inputFile: string, outputFile: string): Promise<{success: boolean, error?: string}> {
  return new Promise((resolve) => {
    const pythonProcess = spawn('python', [
      scriptPath,
      inputFile,
      '--output', outputFile,
      '--max-concurrent', '1'  // Single address, no need for high concurrency
    ], {
      cwd: path.dirname(scriptPath),
      env: {
        ...process.env,
        PYTHONPATH: path.dirname(scriptPath)
      }
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        console.log('📊 Pipeline completed successfully');
        console.log('Pipeline output:', stdout);
        resolve({ success: true });
      } else {
        console.error('❌ Pipeline failed with code:', code);
        console.error('Pipeline stderr:', stderr);
        resolve({ 
          success: false, 
          error: `Pipeline execution failed: ${stderr || 'Unknown error'}` 
        });
      }
    });

    pythonProcess.on('error', (error) => {
      console.error('❌ Pipeline process error:', error);
      resolve({ 
        success: false, 
        error: `Failed to start pipeline: ${error.message}` 
      });
    });

    // Set a timeout for the process (5 minutes)
    setTimeout(() => {
      pythonProcess.kill();
      resolve({ 
        success: false, 
        error: 'Pipeline execution timed out (5 minutes)' 
      });
    }, 5 * 60 * 1000);
  });
}

async function readEnrichedData(outputFile: string): Promise<SkipTraceResult | null> {
  return new Promise((resolve, reject) => {
    const results: any[] = [];
    
    createReadStream(outputFile)
      .pipe(csv())
      .on('data', (data: any) => results.push(data))
      .on('end', () => {
        if (results.length === 0) {
          resolve(null);
          return;
        }
        
        const row = results[0]; // Should only be one row for skip trace
        
        const enrichedData: SkipTraceResult = {
          raw_address: row.raw_address || '',
          canonical_address: row.canonical_address || '',
          attomid: row.attomid || null,
          est_balance: row.est_balance ? parseFloat(row.est_balance) : null,
          available_equity: row.available_equity ? parseFloat(row.available_equity) : null,
          ltv: row.ltv ? parseFloat(row.ltv) : null,
          loans_count: row.loans_count ? parseInt(row.loans_count) : 0,
          processed_at: row.processed_at || new Date().toISOString()
        };
        
        resolve(enrichedData);
      })
      .on('error', (error: any) => {
        reject(error);
      });
  });
}

export async function GET(req: NextRequest) {
  return NextResponse.json({
    message: 'Skip trace API endpoint. Use POST with {"address": "your address"} to get property data.',
    example: {
      method: 'POST',
      body: {
        address: '123 Main Street, Houston, TX 77001'
      }
    }
  });
} 