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
  console.log('=== COBB GA SESSION DEBUG ===');
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
    
    // Check if user has permission for Cobb GA
    if (userExists.userType !== 'COBB_GA') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Cobb GA pulls',
        debug: { userType: userExists.userType, required: 'COBB_GA' }
      }, { status: 403 });
    }
    
    console.log('✅ UserId verified in database with COBB_GA access:', userExists.email);
    
  } catch (dbError) {
    console.error('❌ Database error during user verification:', dbError);
    return NextResponse.json({ 
      error: 'Database connection error',
      debug: { userId, dbError: String(dbError) }
    }, { status: 500 });
  }
  
  try {
    console.log('🕐 Starting 5-second delay before populating Cobb GA data...');
    
    // Wait 5 seconds
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    console.log('✅ 5-second delay completed, now populating data for user:', userId);
    
    // Static CSV data to insert for current user
    const cobbGaRecords = [
      {
        case_number: `COBB-${userId.slice(-4)}-001`,
        document_type: 'Tax Deed',
        filing_date: new Date('2017-01-23'),
        debtor_name: '1005 Cobb Place Blvd., NW, Kennesaw, GA 30144',
        claimant_name: 'N/A',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-002`,
        document_type: 'Tax Deed',
        filing_date: new Date('2024-05-07'),
        debtor_name: '3221 Calcutta Court, Powder Springs, GA',
        claimant_name: 'N/A',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-003`,
        document_type: 'Tax Deed',
        filing_date: new Date('2017-01-13'),
        debtor_name: '2229 Smoke Stone Cir, Marietta, GA 30062',
        claimant_name: '$422,847.21',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-004`,
        document_type: 'Tax Deed',
        filing_date: new Date('2023-11-28'),
        debtor_name: '4803 Howard Drive, Powder Springs, GA 30127',
        claimant_name: '$294,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-005`,
        document_type: 'Tax Deed',
        filing_date: new Date('2023-11-28'),
        debtor_name: '4828 Duncan Drive, Powder Springs, GA 30127',
        claimant_name: '$294,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-006`,
        document_type: 'Tax Deed',
        filing_date: new Date('2006-02-02'),
        debtor_name: '4944 Pippin Dr NW, Acworth, GA 30101',
        claimant_name: '$151,900.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-007`,
        document_type: 'Tax Deed',
        filing_date: new Date('2021-10-05'),
        debtor_name: '330 Anders Path, Marietta, GA 30064',
        claimant_name: '$940,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-008`,
        document_type: 'Tax Deed',
        filing_date: new Date('2006-06-09'),
        debtor_name: '2090 Kolb Ridge Court SW, Marietta, GA 30008',
        claimant_name: '$148,500.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-009`,
        document_type: 'Tax Deed',
        filing_date: new Date('2016-08-22'),
        debtor_name: '4433 Sugar Maple Dr NW, Acworth, GA 30101',
        claimant_name: '$204,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-010`,
        document_type: 'Tax Deed',
        filing_date: new Date('2023-06-08'),
        debtor_name: '4349 Highborne Drive NE, Marietta, GA 30066',
        claimant_name: '$75,000.00 (with a prior Security Deed of $479,751.00 noted)',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-011`,
        document_type: 'Tax Deed',
        filing_date: new Date('2001-12-07'),
        debtor_name: '2915 Sope Creek Drive, Marietta, GA 30068',
        claimant_name: '$136,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-012`,
        document_type: 'Tax Deed',
        filing_date: new Date('2007-05-01'),
        debtor_name: '1392 Waterford Green Dr, Marietta, GA 30068',
        claimant_name: '$546,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-013`,
        document_type: 'Tax Deed',
        filing_date: new Date('2008-01-17'),
        debtor_name: '2200 Hollowbrooke Ct NW, Acworth, GA 30101',
        claimant_name: '$379,852.54',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-014`,
        document_type: 'Tax Deed',
        filing_date: new Date('2006-04-14'),
        debtor_name: '2952 Chipmunk Tr SE, Marietta, GA 30067',
        claimant_name: '$88,493.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-015`,
        document_type: 'Tax Deed',
        filing_date: new Date('1998-02-27'),
        debtor_name: '4251 Sorrells Blvd, Powder Springs, GA 30073',
        claimant_name: '$122,550.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-016`,
        document_type: 'Tax Deed',
        filing_date: new Date('2022-02-25'),
        debtor_name: '5591 and 5595 Edith Street, Austell, GA 30106-3303',
        claimant_name: '$195,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-017`,
        document_type: 'Tax Deed',
        filing_date: new Date('2019-09-05'),
        debtor_name: '2278 Smith Ave SW, Marietta, GA 30064',
        claimant_name: '$218,960.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-018`,
        document_type: 'Tax Deed',
        filing_date: new Date('2019-06-25'),
        debtor_name: '4803 Davitt Ct NW, Acworth, GA 30102',
        claimant_name: '$166,920.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-019`,
        document_type: 'Tax Deed',
        filing_date: new Date('2005-01-05'),
        debtor_name: '2690 Bent Hickory Dr SE, Smyrna, GA 30082',
        claimant_name: '$159,920.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-020`,
        document_type: 'Tax Deed',
        filing_date: new Date('2015-08-10'),
        debtor_name: '3744 Thackary Dr, Powder Springs, GA 30127',
        claimant_name: '$285,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-021`,
        document_type: 'Tax Deed',
        filing_date: new Date('2021-10-18'),
        debtor_name: '2679 Tucson Way, Powder Springs, GA 30127',
        claimant_name: '$260,200.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-022`,
        document_type: 'Tax Deed',
        filing_date: new Date('2020-07-20'),
        debtor_name: '4335 Commodore Rd, Powder Springs, GA 30127',
        claimant_name: '$354,790.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-023`,
        document_type: 'Tax Deed',
        filing_date: new Date('2010-11-16'),
        debtor_name: '4527 Baker Grove Rd, Acworth, GA 30101',
        claimant_name: '$125,113.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-024`,
        document_type: 'Tax Deed',
        filing_date: new Date('2006-07-19'),
        debtor_name: '1452 Seafoam Court, Marietta, GA 30066',
        claimant_name: '$166,250.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-025`,
        document_type: 'Tax Deed',
        filing_date: new Date('2008-01-08'),
        debtor_name: '2670 Bankstone Drive SW, Marietta, GA 30064',
        claimant_name: '$109,350.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-026`,
        document_type: 'Tax Deed',
        filing_date: new Date('2022-08-31'),
        debtor_name: '315 Renae Ln SW, Marietta, GA 30060',
        claimant_name: '$300,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-027`,
        document_type: 'Tax Deed',
        filing_date: new Date('2022-03-21'),
        debtor_name: '4845 Willow St, Acworth, GA',
        claimant_name: '$334,500.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-028`,
        document_type: 'Tax Deed',
        filing_date: new Date('2022-02-02'),
        debtor_name: '2592 Deerfield Circle, Marietta, GA 30064',
        claimant_name: '$159,000.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-029`,
        document_type: 'Tax Deed',
        filing_date: new Date('2008-01-23'),
        debtor_name: '1806 Wynthrop Manor Dr, Marietta, GA 30064',
        claimant_name: '$285,000.00 (with a prior Security Deed of $1,015,000.00 noted)',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-030`,
        document_type: 'Tax Deed',
        filing_date: new Date('2006-03-07'),
        debtor_name: '2833 Golden Club Bend, Austell, GA 30106',
        claimant_name: '$157,500.00',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      },
      {
        case_number: `COBB-${userId.slice(-4)}-031`,
        document_type: 'Tax Deed',
        filing_date: new Date('2025-01-21'),
        debtor_name: '1107 Wynne\'s Ridge Circle, Marietta, GA 30067',
        claimant_name: 'N/A',
        county: 'Cobb GA',
        book_page: '',
        document_link: '',
        state: 'GA',
        userId: userId,
        is_new: true
      }
    ];
    
    // Insert all records for the current user
    const createdRecords = await prisma.cobb_ga_filing.createMany({
      data: cobbGaRecords,
      skipDuplicates: true // Skip if records already exist
    });
    
    console.log(`✅ Successfully created ${createdRecords.count} new Cobb GA records for user ${userId}`);
    
    return NextResponse.json({ 
      success: true, 
      records_created: createdRecords.count,
      message: `Successfully populated ${createdRecords.count} Cobb GA records`
    });
    
  } catch (error) {
    console.error('Failed to populate Cobb GA data:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to populate Cobb GA data' 
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
      where: { id: jobId, userId, job_type: 'COBB_GA_PULL' }
    });
    if (!job) {
      return NextResponse.json({ 
        success: false, 
        error: 'Cobb GA job not found' 
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
    console.error('Failed to get Cobb GA job status:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to get job status' 
    }, { status: 500 });
  }
} 