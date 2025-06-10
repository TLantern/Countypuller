import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  try {
    // Verify user has FULTON_GA access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'FULTON_GA') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Fulton GA records'
      }, { status: 403 });
    }
    
    // Fetch Fulton GA records for this user
    const records = await prisma.fulton_ga_filing.findMany({
      where: { userId },
      orderBy: { created_at: 'desc' },
      take: 1000  // Limit to 1000 records for performance
    });
    
    // Format the data for the frontend
    const formattedRecords = records.map((record: any) => ({
      case_number: record.case_number,
      document_type: record.document_type || '',
      filing_date: record.filing_date ? record.filing_date.toISOString().split('T')[0] : '',
      debtor_name: record.debtor_name || '',
      claimant_name: record.claimant_name || '',
      county: record.county || '',
      book_page: record.book_page || '',
      document_link: record.document_link || '',
      state: record.state || '',
      created_at: record.created_at.toISOString(),
      is_new: record.is_new
    }));
    
    return NextResponse.json(formattedRecords);
  } catch (error) {
    console.error('Error fetching Fulton GA records:', error);
    return NextResponse.json({ 
      error: 'Failed to fetch records' 
    }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  try {
    // Verify user has FULTON_GA access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'FULTON_GA') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Fulton GA records'
      }, { status: 403 });
    }
    
    const { case_number, is_new } = await req.json();
    
    if (!case_number) {
      return NextResponse.json({ 
        error: 'Case number is required' 
      }, { status: 400 });
    }
    
    // Update the record
    const updatedRecord = await prisma.fulton_ga_filing.updateMany({
      where: { 
        case_number: case_number,
        userId: userId
      },
      data: { is_new: is_new }
    });
    
    if (updatedRecord.count === 0) {
      return NextResponse.json({ 
        error: 'Record not found or not owned by user' 
      }, { status: 404 });
    }
    
    return NextResponse.json({ 
      success: true,
      message: 'Record updated successfully'
    });
  } catch (error) {
    console.error('Error updating Fulton GA record:', error);
    return NextResponse.json({ 
      error: 'Failed to update record' 
    }, { status: 500 });
  }
} 