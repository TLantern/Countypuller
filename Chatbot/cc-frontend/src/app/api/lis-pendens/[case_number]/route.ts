import { NextRequest, NextResponse } from 'next/server';
import prisma from '../../../../lib/prisma';
import { getServerSession } from "next-auth";
import { authOptions } from "../../auth/[...nextauth]/route";

export async function PATCH(request: NextRequest) {
  const case_number = request.nextUrl.pathname.split('/').pop();
  const body = await request.json();
  const { is_new } = body;
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  if (!session || !userId) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }
  try {
    const updated = await prisma.lis_pendens_filing.updateMany({
      where: { case_number, userId },
      data: { is_new },
    });
    if (updated.count === 0) {
      return NextResponse.json({ error: 'Record not found or not owned by user' }, { status: 404 });
    }
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to update record', details: String(error) }, { status: 500 });
  }
} 