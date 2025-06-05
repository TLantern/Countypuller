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
    // Verify user has HILLSBOROUGH_NH access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'HILLSBOROUGH_NH') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Hillsborough NH records'
      }, { status: 403 });
    }
    
    // Fetch Hillsborough NH records for this user
    const records = await prisma.hillsborough_nh_filing.findMany({
      where: { userId },
      orderBy: { created_at: 'desc' },
      take: 1000  // Limit to 1000 records for performance
    });
    
    // Format the data for the frontend
    const formattedRecords = records.map((record: any) => ({
      document_number: record.document_number,
      document_url: record.document_url,
      recorded_date: record.recorded_date ? record.recorded_date.toISOString().split('T')[0] : '',
      instrument_type: record.instrument_type || '',
      grantor: record.grantor || '',
      grantee: record.grantee || '',
      property_address: record.property_address || '',
      book_page: record.book_page || '',
      consideration: record.consideration || '',
      legal_description: record.legal_description || '',
      county: record.county || '',
      state: record.state || '',
      filing_date: record.filing_date || '',
      amount: record.amount || '',
      parties: record.parties || '',
      location: record.location || '',
      status: record.status || '',
      created_at: record.created_at.toISOString(),
      is_new: record.is_new,
      doc_type: record.doc_type || ''
    }));
    
    return NextResponse.json(formattedRecords);
  } catch (error) {
    console.error('Error fetching Hillsborough NH records:', error);
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
    // Verify user has HILLSBOROUGH_NH access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'HILLSBOROUGH_NH') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Hillsborough NH records'
      }, { status: 403 });
    }
    
    const { document_number, is_new } = await req.json();
    
    if (!document_number) {
      return NextResponse.json({ 
        error: 'Document number is required' 
      }, { status: 400 });
    }
    
    // Update the record
    const updatedRecord = await prisma.hillsborough_nh_filing.updateMany({
      where: { 
        document_number: document_number,
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
    console.error('Error updating Hillsborough NH record:', error);
    return NextResponse.json({ 
      error: 'Failed to update record' 
    }, { status: 500 });
  }
} 