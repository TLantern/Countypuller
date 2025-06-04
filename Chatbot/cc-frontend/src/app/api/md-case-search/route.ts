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
    // Verify user has MD_CASE_SEARCH access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'MD_CASE_SEARCH') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Maryland Case Search'
      }, { status: 403 });
    }
    
    // Fetch Maryland case search records for this user
    const records = await prisma.md_case_search_filing.findMany({
      where: { userId },
      orderBy: { created_at: 'desc' },
      take: 1000  // Limit to 1000 records for performance
    });
    
    // Format the data for the frontend
    const formattedRecords = records.map(record => ({
      case_number: record.case_number,
      case_url: record.case_url,
      file_date: record.file_date ? record.file_date.toISOString().split('T')[0] : '',
      party_name: record.party_name || '',
      case_type: record.case_type || '',
      county: record.county || '',
      created_at: record.created_at.toISOString(),
      is_new: record.is_new,
      doc_type: record.doc_type || '',
      property_address: record.property_address || '',
      defendant_info: record.defendant_info || ''
    }));
    
    return NextResponse.json(formattedRecords);
  } catch (error) {
    console.error('Error fetching MD case search records:', error);
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
    const { case_number, is_new } = await req.json();
    
    // Update the record
    await prisma.md_case_search_filing.update({
      where: { case_number },
      data: { is_new }
    });
    
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error updating MD case search record:', error);
    return NextResponse.json({ 
      error: 'Failed to update record' 
    }, { status: 500 });
  }
} 