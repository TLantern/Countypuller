import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../../lib/prisma';

export async function PATCH(request: NextRequest) {
  const case_number = request.nextUrl.pathname.split('/').pop();
  const body = await request.json();
  const { is_new } = body;
  try {
    const updated = await prisma.lis_pendens_filing.update({
      where: { case_number },
      data: { is_new },
    });
    return NextResponse.json(updated);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to update record', details: String(error) }, { status: 500 });
  }
} 