import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

export async function POST(req: NextRequest) {
  try {
    const { email, firstName, password } = await req.json();
    if (!email || !firstName || !password) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
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
    return NextResponse.json({ id: user.id, email: user.email, firstName: user.firstName });
  } catch (error) {
    console.error('Error registering user:', error);
    return NextResponse.json({ error: 'Failed to register user' }, { status: 500 });
  }
} 