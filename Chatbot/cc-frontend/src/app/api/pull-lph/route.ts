import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";

// Job status enum
enum JobStatus {
  PENDING = 'PENDING',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED'
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  try {
    // Create a new job record in the database
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'LIS_PENDENS_PULL',
        status: JobStatus.PENDING,
        created_at: new Date(),
        parameters: {
          limit: 10,
          source: 'harris_county'
        },
        userId
      }
    });
    return NextResponse.json({ 
      success: true, 
      job_id: job.id,
      status: job.status,
      message: 'Scraping job queued successfully. Use GET /api/pull-lph/{job_id} to check status.'
    });
  } catch (error) {
    console.error('Failed to create scraping job:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to create scraping job' 
    }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  const url = new URL(req.url);
  const jobId = url.searchParams.get('job_id');
  if (!jobId) {
    return NextResponse.json({ 
      success: false, 
      error: 'job_id parameter is required' 
    }, { status: 400 });
  }
  try {
    const job = await prisma.scraping_job.findFirst({
      where: { id: jobId, userId }
    });
    if (!job) {
      return NextResponse.json({ 
        success: false, 
        error: 'Job not found' 
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
    console.error('Failed to get job status:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to get job status' 
    }, { status: 500 });
  }
} 