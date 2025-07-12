import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

export async function POST(req: NextRequest) {
  try {
    const { email, firstName, password } = await req.json();
    
    // Validate required fields
    if (!email || !firstName || !password) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return NextResponse.json({ error: 'Invalid email format' }, { status: 400 });
    }
    
    // Validate password strength
    if (password.length < 6) {
      return NextResponse.json({ error: 'Password must be at least 6 characters long' }, { status: 400 });
    }
    
    // Check if user already exists
    const existingUser = await prisma.user.findUnique({ where: { email } });
    if (existingUser) {
      return NextResponse.json({ error: 'Email already in use' }, { status: 409 });
    }
    
    // Hash the password
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Create the user
    const user = await prisma.user.create({
      data: {
        email,
        firstName,
        password: hashedPassword,
      },
    });
    
    // Return user data without password
    return NextResponse.json({ 
      id: user.id, 
      email: user.email, 
      firstName: user.firstName 
    });
  } catch (error) {
    console.error('Error registering user:', error);
    
    // Handle specific Prisma errors
    if (error && typeof error === 'object' && 'code' in error) {
      const prismaError = error as any;
      
      // Handle unique constraint violations
      if (prismaError.code === 'P2002') {
        return NextResponse.json({ error: 'Email already in use' }, { status: 409 });
      }
      
      // Handle validation errors
      if (prismaError.code === 'P2000') {
        return NextResponse.json({ error: 'Invalid data provided' }, { status: 400 });
      }
      
      // Handle connection errors
      if (prismaError.code === 'P1001') {
        return NextResponse.json({ error: 'Database connection failed. Please try again later.' }, { status: 500 });
      }
    }
    
    // Handle general errors
    if (error instanceof Error) {
      if (error.message.includes('email')) {
        return NextResponse.json({ error: 'Email validation failed' }, { status: 400 });
      }
      if (error.message.includes('password')) {
        return NextResponse.json({ error: 'Password validation failed' }, { status: 400 });
      }
    }
    
    return NextResponse.json({ error: 'Registration failed. Please try again.' }, { status: 500 });
  } finally {
    await prisma.$disconnect();
  }
} 