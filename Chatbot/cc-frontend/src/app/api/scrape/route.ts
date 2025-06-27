import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import prisma from '../../../lib/prisma';

// Job status enum
const JobStatus = {
  PENDING: 'PENDING',
  IN_PROGRESS: 'IN_PROGRESS',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED'
} as const;

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    const body = await request.json();
    const { county, filters } = body;

    // Validate required fields
    if (!county) {
      return NextResponse.json({ error: 'County is required' }, { status: 400 });
    }

    // Default filters if not provided
    const defaultFilters = {
      documentType: 'LisPendens',
      dateFrom: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
      dateTo: new Date().toISOString().split('T')[0], // today
      pageSize: 50
    };

    const mergedFilters = { ...defaultFilters, ...filters };

    // Create a new job record in the database
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'AGENT_SCRAPE',
        status: JobStatus.PENDING,
        created_at: new Date(),
        parameters: {
          county,
          filters: mergedFilters
        },
        userId
      }
    });

    return NextResponse.json({ 
      success: true, 
      job_id: job.id,
      status: job.status,
      message: 'Agent scraping job queued successfully. Use GET /api/scrape?job_id={job_id} to check status.'
    });
  } catch (error) {
    console.error('Scrape API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) }, 
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  const url = new URL(request.url);
  const jobId = url.searchParams.get('job_id');
  
  if (!jobId) {
    return NextResponse.json({ 
      success: false, 
      error: 'job_id parameter is required' 
    }, { status: 400 });
  }
  
  try {
    const job = await prisma.scraping_job.findFirst({
      where: { id: jobId, userId, job_type: 'AGENT_SCRAPE' }
    });
    
    if (!job) {
      return NextResponse.json({ 
        success: false, 
        error: 'Agent scraping job not found' 
      }, { status: 404 });
    }
    
    return NextResponse.json({ 
      success: true, 
      job_id: job.id,
      status: job.status,
      created_at: job.created_at,
      completed_at: job.completed_at,
      result: job.result,
      error_message: job.error_message,
      records_processed: job.records_processed
    });
  } catch (error) {
    console.error('Failed to get agent scraping job status:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to get job status' 
    }, { status: 500 });
  }
} 