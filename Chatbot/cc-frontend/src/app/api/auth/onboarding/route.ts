import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth/next';
import { authOptions } from '../[...nextauth]/authOptions';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// GET - Check if user has completed onboarding
export async function GET(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { hasCompletedOnboarding: true }
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    return NextResponse.json({ 
      hasCompletedOnboarding: user.hasCompletedOnboarding 
    });

  } catch (error) {
    console.error('Error checking onboarding status:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

// POST - Mark onboarding as completed
export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { county, docTypes } = await req.json();

    // Update user's onboarding status in database
    const updatedUser = await prisma.user.update({
      where: { id: userId },
      data: { hasCompletedOnboarding: true },
      select: { 
        id: true, 
        email: true, 
        hasCompletedOnboarding: true 
      }
    });

    return NextResponse.json({ 
      success: true,
      user: updatedUser,
      message: 'Onboarding completed successfully'
    });

  } catch (error) {
    console.error('Error updating onboarding status:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 