import { NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/route";

export async function GET() {
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  try {
    const filings = await prisma.lis_pendens_filing.findMany({
      where: { userId },
      orderBy: { created_at: 'desc' }
    });
    return NextResponse.json(filings);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch filings' }, { status: 500 });
  }
}