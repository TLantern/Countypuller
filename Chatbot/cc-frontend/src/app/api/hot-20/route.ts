import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/authOptions';
import { PrismaClient } from '@prisma/client';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const prisma = new PrismaClient();

interface PropertyWithEquity {
  id: string;
  property_address: string;
  case_number?: string;
  document_number?: string;
  raw_address: string;
  canonical_address: string;
  attomid?: string;
  est_balance?: number;
  available_equity?: number;
  ltv?: number;
  market_value?: number;
  loans_count?: number;
  processed_at: string;
  original_record: any;
}

export async function POST(request: NextRequest) {
  try {
    // Check authentication
    const session = await getServerSession(authOptions);
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { userType, properties: currentProperties } = await request.json();

    if (!userType) {
      return NextResponse.json({ error: 'User type is required' }, { status: 400 });
    }

    if (!currentProperties || !Array.isArray(currentProperties)) {
      return NextResponse.json({ error: 'Properties array is required' }, { status: 400 });
    }

    console.log(`Starting Hot 20 analysis for ${currentProperties.length} current dashboard properties`);

    // Filter properties that have addresses
    const properties = currentProperties.filter(prop => prop.address && prop.address.trim());

    if (properties.length === 0) {
      return NextResponse.json({ 
        success: true, 
        data: [], 
        message: 'No properties found with addresses in current dashboard data' 
      });
    }

    console.log(`Found ${properties.length} properties with addresses to analyze`);

    // Step 2: Create CSV file with all addresses
    const tempDir = path.join(process.cwd(), 'scripts', 'temp');
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const csvFileName = `hot20_${userType}_${Date.now()}.csv`;
    const csvFilePath = path.join(tempDir, csvFileName);

    // Create CSV content
    const csvHeaders = 'address\n';
    const csvRows = properties
      .map(p => `"${p.address.replace(/"/g, '""')}"`)
      .join('\n');
    
    const csvContent = csvHeaders + csvRows;
    fs.writeFileSync(csvFilePath, csvContent);

    console.log(`Created CSV file: ${csvFilePath} with ${properties.length} addresses`);

    // Step 3: Run address enrichment pipeline
    const pythonScript = path.join(process.cwd(), 'scripts', 'address_enrichment_pipeline.py');
    const outputFileName = `hot20_output_${userType}_${Date.now()}.csv`;
    const outputFilePath = path.join(tempDir, outputFileName);

         await new Promise<void>((resolve, reject) => {
       const pythonProcess = spawn('python3', [
         pythonScript,
         csvFilePath,
         '--output', outputFilePath
       ], {
        cwd: path.join(process.cwd(), 'scripts'),
        env: {
          ...process.env,
          GOOGLE_MAPS_API_KEY: process.env.GOOGLE_MAPS_API_KEY,
          ATTOM_API_KEY: process.env.ATTOM_API_KEY,
          USPS_USER_ID: process.env.USPS_USER_ID
        }
      });

      let stdout = '';
      let stderr = '';

      pythonProcess.stdout?.on('data', (data) => {
        stdout += data.toString();
        console.log('Python stdout:', data.toString());
      });

      pythonProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
        console.log('Python stderr:', data.toString());
      });

      pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code: ${code}`);
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Python process failed with code ${code}\nStderr: ${stderr}`));
        }
      });

      pythonProcess.on('error', (error) => {
        console.error('Python process error:', error);
        reject(error);
      });
    });

    // Step 4: Read and parse the enriched results
    let enrichedResults: PropertyWithEquity[] = [];
    
    if (fs.existsSync(outputFilePath)) {
      console.log(`Reading enrichment results from: ${outputFilePath}`);
      const outputContent = fs.readFileSync(outputFilePath, 'utf-8');
      console.log(`Output file content:\n${outputContent}`);
      
      const lines = outputContent.split('\n').filter(line => line.trim());
      console.log(`Found ${lines.length} lines in output file`);
      
      if (lines.length > 1) { // Skip header row
        const headerLine = lines[0];
        console.log(`Header line: ${headerLine}`);
        
        // Better CSV parsing that handles quoted fields
        const parseCSVLine = (line: string): string[] => {
          const result: string[] = [];
          let current = '';
          let inQuotes = false;
          
          for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (char === '"') {
              inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
              result.push(current.trim());
              current = '';
            } else {
              current += char;
            }
          }
          result.push(current.trim());
          return result;
        };
        
        const headers = parseCSVLine(headerLine);
        console.log(`Parsed headers:`, headers);
        
        for (let i = 1; i < lines.length; i++) {
          const line = lines[i];
          console.log(`Processing line ${i}: ${line}`);
          
          const values = parseCSVLine(line);
          console.log(`Parsed values:`, values);
          
          if (values.length >= headers.length) {
            const result: any = {};
            headers.forEach((header, index) => {
              result[header] = values[index] || null;
            });
            
            console.log(`Parsed result:`, result);

            // Find the original property record
            const originalProperty = properties.find(p => 
              p.address && 
              (result.raw_address?.includes(p.address) || 
               p.address.includes(result.raw_address) ||
               result.raw_address?.toLowerCase().includes(p.address.toLowerCase()) ||
               p.address.toLowerCase().includes(result.raw_address?.toLowerCase() || ''))
            );

            console.log(`Original property found:`, originalProperty ? 'YES' : 'NO');
            console.log(`Available equity:`, result.available_equity);

            // Include all results with ATTOM data (not just equity > 0)
            if (result.attomid && result.attomid !== 'null' && result.attomid !== '') {
              const equity = result.available_equity ? parseFloat(result.available_equity) : 0;
              const balance = result.est_balance ? parseFloat(result.est_balance) : 0;
              const ltv = result.ltv ? parseFloat(result.ltv) : 0;
              
              console.log(`Adding property with equity: ${equity}, balance: ${balance}, ltv: ${ltv}`);
              
              enrichedResults.push({
                id: originalProperty?.id || `property_${i}`,
                property_address: result.raw_address || '',
                case_number: originalProperty?.original_record?.case_number,
                document_number: originalProperty?.original_record?.document_number,
                raw_address: result.raw_address || '',
                canonical_address: result.canonical_address || '',
                attomid: result.attomid,
                est_balance: balance || undefined,
                available_equity: equity || undefined,
                ltv: ltv || undefined,
                market_value: result.market_value ? parseFloat(result.market_value) : undefined,
                loans_count: result.loans_count ? parseInt(result.loans_count) : undefined,
                processed_at: result.processed_at || new Date().toISOString(),
                original_record: originalProperty?.original_record
              });
            } else {
              console.log(`Skipping property - no ATTOM ID found`);
            }
          } else {
            console.log(`Skipping line ${i} - insufficient values (${values.length} < ${headers.length})`);
          }
        }
      } else {
        console.log('No data lines found in output file');
      }
    } else {
      console.log(`Output file does not exist: ${outputFilePath}`);
    }
    
    console.log(`Total enriched results found: ${enrichedResults.length}`);

    // Step 5: Rank by equity (high to low) and LTV (low to high)
    const rankedResults = enrichedResults
      .filter(result => result.attomid) // Only include properties with ATTOM data
      .sort((a, b) => {
        // Primary sort: Higher equity first (including $0 equity)
        const equityDiff = (b.available_equity || 0) - (a.available_equity || 0);
        if (Math.abs(equityDiff) > 1000) { // If equity difference is significant (> $1000)
          return equityDiff;
        }
        
        // Secondary sort: Lower LTV first (if equity is similar)
        return (a.ltv || 1) - (b.ltv || 1);
      })
      .slice(0, 20); // Take top 20

    console.log(`Hot 20 analysis complete. Found ${rankedResults.length} properties with equity data`);

    // Step 6: Clean up temporary files
    try {
      if (fs.existsSync(csvFilePath)) fs.unlinkSync(csvFilePath);
      if (fs.existsSync(outputFilePath)) fs.unlinkSync(outputFilePath);
    } catch (cleanupError) {
      console.warn('Failed to clean up temporary files:', cleanupError);
    }

    return NextResponse.json({
      success: true,
      data: rankedResults,
      summary: {
        total_properties_analyzed: properties.length,
        properties_with_equity: enrichedResults.filter(r => (r.available_equity || 0) > 0).length,
        hot_20_count: rankedResults.length,
        avg_equity: rankedResults.length > 0 ? rankedResults.reduce((sum, p) => sum + (p.available_equity || 0), 0) / rankedResults.length : 0,
        avg_ltv: rankedResults.length > 0 ? rankedResults.reduce((sum, p) => sum + (p.ltv || 0), 0) / rankedResults.length : 0
      }
    });

  } catch (error) {
    console.error('Hot 20 analysis error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    }, { status: 500 });
  }
} 