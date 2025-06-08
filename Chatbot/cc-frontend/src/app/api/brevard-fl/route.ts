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
    // Verify user has BREVARD_FL access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'BREVARD_FL') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Brevard FL records'
      }, { status: 403 });
    }
    
    // Fetch Brevard FL records for this user
    const records = await prisma.brevard_fl_filing.findMany({
      where: { userId },
      orderBy: { created_at: 'desc' },
      take: 1000  // Limit to 1000 records for performance
    });
    
    // Format the data for the frontend
    const formattedRecords = records.map((record: any) => ({
      case_number: record.case_number,
      document_url: record.document_url,
      file_date: record.file_date ? record.file_date.toISOString().split('T')[0] : '',
      case_type: record.case_type || '',
      party_name: record.party_name || '',
      property_address: record.property_address || '',
      county: record.county || '',
      created_at: record.created_at.toISOString(),
      is_new: record.is_new
    }));
    
    return NextResponse.json(formattedRecords);
  } catch (error) {
    console.error('Error fetching Brevard FL records:', error);
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
    // Verify user has BREVARD_FL access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user || user.userType !== 'BREVARD_FL') {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Brevard FL records'
      }, { status: 403 });
    }
    
    const { case_number, is_new } = await req.json();
    
    if (!case_number) {
      return NextResponse.json({ 
        error: 'Case number is required' 
      }, { status: 400 });
    }
    
    // Update the record
    const updatedRecord = await prisma.brevard_fl_filing.updateMany({
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
    console.error('Error updating Brevard FL record:', error);
    return NextResponse.json({ 
      error: 'Failed to update record' 
    }, { status: 500 });
  }
} 