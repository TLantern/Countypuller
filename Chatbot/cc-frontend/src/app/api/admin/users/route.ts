import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../../auth/[...nextauth]/authOptions";

// Admin users who can manage all account types
const ADMIN_EMAILS = ['Teniola101@outlook.com'];

function isAdmin(userEmail: string | null | undefined): boolean {
  return userEmail ? ADMIN_EMAILS.includes(userEmail) : false;
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions);
  
  if (!session || !session.user?.email) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  if (!isAdmin(session.user.email)) {
    return NextResponse.json({ error: 'Admin access required' }, { status: 403 });
  }
  
  try {
    const users = await prisma.user.findMany({
      select: { 
        id: true, 
        email: true, 
        userType: true, 
        createdAt: true 
      },
      orderBy: { createdAt: 'desc' }
    });
    
    return NextResponse.json({ users });
  } catch (error) {
    console.error('Error fetching users:', error);
    return NextResponse.json({ 
      error: 'Failed to fetch users' 
    }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions);
  
  if (!session || !session.user?.email) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  
  if (!isAdmin(session.user.email)) {
    return NextResponse.json({ error: 'Admin access required' }, { status: 403 });
  }
  
  try {
    const { userId, userType } = await req.json();
    
    // Validate inputs
    if (!userId || !userType) {
      return NextResponse.json({ 
        error: 'User ID and user type are required' 
      }, { status: 400 });
    }
    
    // Validate userType
    if (!['LPH', 'MD_CASE_SEARCH'].includes(userType)) {
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
      user: updatedUser,
      message: `User ${updatedUser.email} updated to ${userType === 'MD_CASE_SEARCH' ? 'Maryland Case Search' : 'Lis Pendens (LPH)'}`
    });
  } catch (error) {
    console.error('Error updating user type:', error);
    return NextResponse.json({ 
      error: 'Failed to update user type' 
    }, { status: 500 });
  }
} 