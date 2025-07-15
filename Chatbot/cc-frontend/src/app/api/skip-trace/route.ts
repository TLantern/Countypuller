import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import csv from 'csv-parser';
import { createReadStream } from 'fs';
import { PrismaClient } from '@prisma/client';
import crypto from 'crypto';
import { enrichAddressFallback } from '../../../lib/address-enrichment';

const prisma = new PrismaClient();

interface SkipTraceResult {
  raw_address: string;
  canonical_address: string;
  attomid: string | null;
  est_balance: number | null;
  available_equity: number | null;
  ltv: number | null;
  market_value: number | null;
  loans_count: number;
  owner_name: string | null;
  primary_email: string | null;
  primary_phone: string | null;
  processed_at: string;
}

interface SkipTraceResponse {
  success: boolean;
  data?: SkipTraceResult;
  error?: string;
  message?: string;
  fromCache?: boolean;
}

// Helper function to normalize address for consistent hashing
function normalizeAddress(address: string): string {
  return address
    .toLowerCase()
    .replace(/[^\w\s]/g, ' ')  // Remove special characters
    .replace(/\s+/g, ' ')      // Normalize whitespace
    .trim();
}

// Generate hash for efficient address lookups
function generateAddressHash(address: string): string {
  const normalized = normalizeAddress(address);
  return crypto.createHash('md5').update(normalized).digest('hex');
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

    // Generate address hash for lookup
    const addressHash = generateAddressHash(address);
    
    // Check if we already have results for this address
    const existingResult = await prisma.skipTraceResult.findFirst({
      where: {
        OR: [
          { address_hash: addressHash },
          { raw_address: address },
          { canonical_address: address }
        ],
        userId: userId
      },
      orderBy: { created_at: 'desc' }
    });

    if (existingResult) {
      console.log(`✅ Found existing skip trace result for address: ${address}`);
      
      // Convert database result to expected format
      const cachedResult: SkipTraceResult = {
        raw_address: existingResult.raw_address,
        canonical_address: existingResult.canonical_address,
        attomid: existingResult.attomid,
        est_balance: existingResult.est_balance ? Number(existingResult.est_balance) : null,
        available_equity: existingResult.available_equity ? Number(existingResult.available_equity) : null,
        ltv: existingResult.ltv ? Number(existingResult.ltv) : null,
        market_value: existingResult.market_value ? Number(existingResult.market_value) : null,
        loans_count: existingResult.loans_count || 0,
        owner_name: existingResult.owner_name,
        primary_email: existingResult.primary_email,
        primary_phone: existingResult.primary_phone,
        processed_at: existingResult.processed_at.toISOString()
      };

      return NextResponse.json({
        success: true,
        data: cachedResult,
        message: 'Cached skip trace result retrieved successfully',
        fromCache: true
      });
    }

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
    // Use /tmp for serverless environments (Vercel, etc.) or fallback to local temp
    const tempDir = process.env.VERCEL || process.env.NODE_ENV === 'production' 
      ? '/tmp' 
      : path.join(scriptsDir, 'temp');
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

      // Try to run the Python pipeline first, fallback to Node.js if it fails
      let enrichedData: SkipTraceResult | null = null;
      
      try {
        // Run the address enrichment pipeline
        const pipelineScript = path.join(scriptsDir, 'address_enrichment_pipeline.py');
        
        const result = await runPipeline(pipelineScript, inputFile, outputFile);

        if (result.success) {
          // Check if output file exists before trying to read it
          try {
            await fs.access(outputFile);
            enrichedData = await readEnrichedData(outputFile);
          } catch (error) {
            console.warn('Pipeline completed but output file could not be read:', error);
          }
        }
      } catch (pipelineError) {
        console.warn('Python pipeline failed, using Node.js fallback:', pipelineError);
      }

      // If Python pipeline failed or returned no data, try Python serverless function
      if (!enrichedData) {
        try {
          console.log('🔄 Trying Python serverless function...');
          const baseUrl = process.env.NEXTAUTH_URL || 'https://clerkcrawler.com';
          const pythonResponse = await fetch(`${baseUrl}/api/python-enrichment`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ address }),
          });

          if (pythonResponse.ok) {
            const pythonResult = await pythonResponse.json();
            enrichedData = {
              raw_address: address,
              canonical_address: pythonResult.canonical_address || address,
              attomid: pythonResult.attomid || null,
              est_balance: pythonResult.est_balance || null,
              available_equity: pythonResult.available_equity || null,
              ltv: pythonResult.ltv || null,
              market_value: pythonResult.market_value || null,
              loans_count: pythonResult.loans_count || 0,
              owner_name: pythonResult.owner_name || null,
              primary_email: pythonResult.primary_email || null,
              primary_phone: pythonResult.primary_phone || null,
              processed_at: new Date().toISOString()
            };
            console.log('✅ Python serverless function succeeded');
          }
        } catch (pythonError) {
          console.warn('❌ Python serverless function failed:', pythonError);
        }
      }

      // If both Python options failed, use Node.js fallback
      if (!enrichedData) {
        console.log('🔄 Using Node.js fallback for address enrichment');
        const fallbackResult = await enrichAddressFallback(address);
        
        enrichedData = {
          raw_address: fallbackResult.raw_address,
          canonical_address: fallbackResult.canonical_address,
          attomid: fallbackResult.attomid || null,
          est_balance: fallbackResult.est_balance || null,
          available_equity: fallbackResult.available_equity || null,
          ltv: fallbackResult.ltv || null,
          market_value: fallbackResult.market_value || null,
          loans_count: fallbackResult.loans_count || 0,
          owner_name: fallbackResult.owner_name || null,
          primary_email: null, // Not available in fallback
          primary_phone: null, // Not available in fallback
          processed_at: fallbackResult.processed_at
        };
      }

      if (!enrichedData) {
        throw new Error('Both Python pipeline and Node.js fallback failed');
      }

      // Save result to database for future lookups
      try {
        await prisma.skipTraceResult.create({
          data: {
            raw_address: enrichedData.raw_address,
            canonical_address: enrichedData.canonical_address,
            address_hash: addressHash,
            attomid: enrichedData.attomid,
            est_balance: enrichedData.est_balance,
            available_equity: enrichedData.available_equity,
            ltv: enrichedData.ltv,
            market_value: enrichedData.market_value,
            loans_count: enrichedData.loans_count,
            owner_name: enrichedData.owner_name,
            primary_email: enrichedData.primary_email,
            primary_phone: enrichedData.primary_phone,
            userId: userId
          }
        });
        console.log(`💾 Saved skip trace result to database`);
      } catch (dbError) {
        console.warn('Failed to save skip trace result to database:', dbError);
        // Continue anyway - we still have the result
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
        message: 'Skip trace completed successfully',
        fromCache: false
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
    // Try different Python executables based on environment
    const pythonExecutable = process.env.PYTHON_EXECUTABLE || 
                             process.env.VERCEL_PYTHON_PATH || 
                             'python3';
    
    console.log(`🐍 Using Python executable: ${pythonExecutable}`);
    
    const pythonProcess = spawn(pythonExecutable, [
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
      
      // Handle specific error cases
      let errorMessage = error.message;
      if (error.message.includes('ENOENT') || error.message.includes('spawn python3')) {
        errorMessage = 'Python 3 not available in this environment. Using Node.js fallback.';
      }
      
      resolve({ 
        success: false, 
        error: errorMessage
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
          market_value: row.market_value ? parseFloat(row.market_value) : null,
          loans_count: row.loans_count ? parseInt(row.loans_count) : 0,
          owner_name: row.owner_name || null,
          primary_email: row.primary_email || null,
          primary_phone: row.primary_phone || null,
          processed_at: row.processed_at || new Date().toISOString()
        };
        
        resolve(enrichedData);
      })
      .on('error', (error: any) => {
        reject(error);
      });
  });
}

// Add a new GET endpoint to check if address has been skip traced
export async function GET(req: NextRequest): Promise<NextResponse> {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ 
        success: false, 
        error: 'Not authenticated' 
      }, { status: 401 });
    }

    const { searchParams } = new URL(req.url);
    const address = searchParams.get('address');

    if (!address) {
      return NextResponse.json({ 
        success: false, 
        error: 'Address parameter is required' 
      }, { status: 400 });
    }

    const addressHash = generateAddressHash(address);
    
    const existingResult = await prisma.skipTraceResult.findFirst({
      where: {
        OR: [
          { address_hash: addressHash },
          { raw_address: address },
          { canonical_address: address }
        ],
        userId: userId
      },
      select: {
        id: true,
        raw_address: true,
        canonical_address: true,
        processed_at: true
      },
      orderBy: { created_at: 'desc' }
    });

    return NextResponse.json({
      success: true,
      hasResult: !!existingResult,
      result: existingResult || null
    });

  } catch (error) {
    console.error('Skip trace check error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'An unexpected error occurred'
    }, { status: 500 });
  }
} 