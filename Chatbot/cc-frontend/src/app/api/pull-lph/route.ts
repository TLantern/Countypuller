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
  
  // Parse request body to get dateFilter parameter
  let requestBody;
  try {
    requestBody = await req.json();
  } catch (error) {
    // If no body or invalid JSON, use defaults
    requestBody = {};
  }
  
  const dateFilter = requestBody.dateFilter || 7; // Default to 7 days if not provided
  
  // Add comprehensive logging for debugging
  console.log('=== SESSION DEBUG ===');
  console.log('Full session object:', JSON.stringify(session, null, 2));
  console.log('Extracted userId:', userId);
  console.log('UserId type:', typeof userId);
  console.log('UserId length:', userId ? userId.length : 'null');
  console.log('Date filter:', dateFilter, 'days');
  console.log('NODE_ENV:', process.env.NODE_ENV);
  console.log('NEXTAUTH_URL:', process.env.NEXTAUTH_URL);
  
  if (!session || !userId) {
    console.log('❌ Authentication failed - no session or userId');
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  // Verify the userId exists in database before creating job
  try {
    const userExists = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, email: true, userType: true }
    });
    
    console.log('User lookup result:', userExists);
    
    if (!userExists) {
      console.log('❌ UserId from session does not exist in database!');
      return NextResponse.json({ 
        error: 'User session invalid - please login again',
        debug: { sessionUserId: userId, userExists: false }
      }, { status: 401 });
    }
    
    // Check if user has permission for LPH
    if (userExists.userType !== 'LPH') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Lis Pendens pulls',
        debug: { userType: userExists.userType, required: 'LPH' }
      }, { status: 403 });
    }
    
    console.log('✅ UserId verified in database:', userExists.email);
    
  } catch (dbError) {
    console.error('❌ Database error during user verification:', dbError);
    return NextResponse.json({ 
      error: 'Database connection error',
      debug: { userId, dbError: String(dbError) }
    }, { status: 500 });
  }
  
  console.log("Session:", session);
  console.log("userId:", userId);
  try {
    // Calculate dynamic limit based on date range (more days = potentially more records)
    const dynamicLimit = Math.min(100, Math.max(10, Math.floor(dateFilter * 2))); // Scale with date range, cap at 100
    
    // Create a new job record in the database
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'LIS_PENDENS_PULL',
        status: JobStatus.PENDING,
        created_at: new Date(),
        parameters: {
          limit: dynamicLimit,
          dateFilter: dateFilter,
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