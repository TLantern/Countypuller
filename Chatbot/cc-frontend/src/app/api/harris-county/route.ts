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
    // Verify user has LPH access (Harris County users)
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    // Allow both legacy LPH users and new AGENT_SCRAPER users
    const allowedTypes = ['LPH', 'AGENT', 'AGENT_SCRAPER', 'ADMIN'];
    if (!user || !allowedTypes.includes(user.userType)) {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Harris County records'
      }, { status: 403 });
    }
    
    // Fetch Harris County records using Prisma
    const records = await prisma.harris_county_filing.findMany({
      where: { userId: userId },
      orderBy: { created_at: 'desc' },
      take: 1000
    });
    
    // Format the data for the frontend
    const formattedRecords = records.map((record) => ({
      case_number: record.case_number,
      filing_date: record.filing_date ? record.filing_date.toISOString().split('T')[0] : '',
      doc_type: record.doc_type || 'L/P',
      subdivision: record.subdivision || '',
      section: record.section || '',
      block: record.block || '',
      lot: record.lot || '',
      property_address: record.property_address || '',
      parcel_id: record.parcel_id || '',
      ai_summary: record.ai_summary || '',
      county: record.county || 'Harris',
      state: record.state || 'TX',
      created_at: record.created_at.toISOString(),
      is_new: record.is_new
    }));
    
    return NextResponse.json(formattedRecords);
  } catch (error) {
    console.error('Error fetching Harris County records:', error);
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
    // Verify user has LPH access
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    // Allow both legacy LPH users and new AGENT_SCRAPER users
    const allowedTypes = ['LPH', 'AGENT', 'AGENT_SCRAPER', 'ADMIN'];
    if (!user || !allowedTypes.includes(user.userType)) {
      return NextResponse.json({ 
        error: 'Access denied - user not authorized for Harris County records'
      }, { status: 403 });
    }
    
    const { case_number, is_new } = await req.json();
    
    if (!case_number) {
      return NextResponse.json({ 
        error: 'Case number is required' 
      }, { status: 400 });
    }
    
    // Update the record
    const updatedRecord = await prisma.harris_county_filing.updateMany({
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
    console.error('Error updating Harris County record:', error);
    return NextResponse.json({ 
      error: 'Failed to update record' 
    }, { status: 500 });
  }
} 