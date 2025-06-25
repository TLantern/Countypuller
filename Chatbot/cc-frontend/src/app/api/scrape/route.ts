import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import { agentScrape } from '../../../../lib/agents/agent-core';

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    
    if (!session || !userId) {
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    const body = await request.json();
    const { county, filters } = body;

    // Validate required fields
    if (!county) {
      return NextResponse.json({ error: 'County is required' }, { status: 400 });
    }

    // Default filters if not provided
    const defaultFilters = {
      documentType: 'LisPendens',
      dateFrom: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
      dateTo: new Date().toISOString().split('T')[0], // today
      pageSize: 50
    };

    const mergedFilters = { ...defaultFilters, ...filters };

    // Call the agent scraper
    const result = await agentScrape({ 
      county, 
      filters: mergedFilters,
      userId 
    });

    return NextResponse.json(result);
  } catch (error) {
    console.error('Scrape API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) }, 
      { status: 500 }
    );
  }
} 