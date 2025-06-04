import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../[...nextauth]/authOptions";

// Admin users who can manage all account types
const ADMIN_EMAILS = ['Teniola101@outlook.com'];

function isAdmin(userEmail: string | null | undefined): boolean {
  return userEmail ? ADMIN_EMAILS.includes(userEmail) : false;
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { userType: true }
    });
    
    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }
    
    return NextResponse.json({ userType: user.userType });
  } catch (error) {
    console.error('Error fetching user type:', error);
    return NextResponse.json({ 
      error: 'Failed to fetch user type' 
    }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  
  if (!session || !userId || !session.user?.email) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  // Only admin users can change account types
  if (!isAdmin(session.user.email)) {
    return NextResponse.json({ 
      error: 'Access denied. Only administrators can change account types.' 
    }, { status: 403 });
  }
  
  try {
    const { userType } = await req.json();
    
    // Validate userType
    if (!userType || !['LPH', 'MD_CASE_SEARCH'].includes(userType)) {
      return NextResponse.json({ 
        error: 'Invalid user type. Must be LPH or MD_CASE_SEARCH' 
      }, { status: 400 });
    }
    
    // Update user type
    const updatedUser = await prisma.user.update({
      where: { id: userId },
      data: { userType },
      select: { id: true, email: true, userType: true }
    });
    
    if (!updatedUser) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }
    
    return NextResponse.json({ 
      success: true, 
      userType: updatedUser.userType,
      message: 'User type updated successfully'
    });
  } catch (error) {
    console.error('Error updating user type:', error);
    return NextResponse.json({ 
      error: 'Failed to update user type' 
    }, { status: 500 });
  }
} 