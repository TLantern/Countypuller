import { NextResponse } from 'next/server';
import prisma from '../../../lib/prisma';

export async function GET() {
  try {
    const filings = await prisma.lis_pendens_filing.findMany({
      orderBy: { created_at: 'desc' }
    });
    return NextResponse.json(filings);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch filings' }, { status: 500 });
  }
}