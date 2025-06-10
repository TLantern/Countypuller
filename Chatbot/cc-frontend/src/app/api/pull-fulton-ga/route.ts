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
  console.log('=== FULTON GA SESSION DEBUG ===');
  console.log('Full session object:', JSON.stringify(session, null, 2));
  console.log('Extracted userId:', userId);
  console.log('UserId type:', typeof userId);
  console.log('UserId length:', userId ? userId.length : 'null');
  console.log('Date filter:', dateFilter, 'days');
  
  if (!session || !userId) {
    console.log('❌ Authentication failed - no session or userId');
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  // Verify the userId exists in database and check user type
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
    
    // Check if user has permission for Fulton GA
    if (userExists.userType !== 'FULTON_GA') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Fulton GA pulls',
        debug: { userType: userExists.userType, required: 'FULTON_GA' }
      }, { status: 403 });
    }
    
    console.log('✅ UserId verified in database with FULTON_GA access:', userExists.email);
    
  } catch (dbError) {
    console.error('❌ Database error during user verification:', dbError);
    return NextResponse.json({ 
      error: 'Database connection error',
      debug: { userId, dbError: String(dbError) }
    }, { status: 500 });
  }
  
  try {
    // Calculate dynamic limit based on date range (more days = potentially more records)
    const dynamicLimit = 5; // Fixed to 5 records per pull
    
    // Create a new job record in the database
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'FULTON_GA_PULL',
        status: JobStatus.PENDING,
        created_at: new Date(),
        parameters: {
          limit: dynamicLimit,
          dateFilter: dateFilter,
          source: 'fulton_ga_gsccca',
          extract_addresses: true
        },
        userId
      }
    });
    return NextResponse.json({ 
      success: true, 
      job_id: job.id,
      status: job.status,
      message: 'Fulton GA scraping job queued successfully. Use GET /api/pull-fulton-ga/{job_id} to check status.'
    });
  } catch (error) {
    console.error('Failed to create Fulton GA scraping job:', error);
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
      where: { id: jobId, userId, job_type: 'FULTON_GA_PULL' }
    });
    if (!job) {
      return NextResponse.json({ 
        success: false, 
        error: 'Fulton GA job not found' 
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
    console.error('Failed to get Fulton GA job status:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to get job status' 
    }, { status: 500 });
  }
} 