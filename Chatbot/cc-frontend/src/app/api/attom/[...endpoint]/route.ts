import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest, { params }: { params: { endpoint: string[] } }) {
  const apiKey = process.env.ATTOM_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'ATTOM API key not configured' }, { status: 500 });
  }

  // Build the ATTOM endpoint path
  const endpointPath = params.endpoint.join('/');
  const attomBaseUrl = 'https://api.gateway.attomdata.com/propertyapi/v1.0.0/';
  const attomUrl = attomBaseUrl + endpointPath + (req.nextUrl.search ? req.nextUrl.search : '');

  try {
    const attomRes = await fetch(attomUrl, {
      headers: {
        'apikey': apiKey,
        'accept': 'application/json',
      },
    });

    if (!attomRes.ok) {
      const error = await attomRes.text();
      return NextResponse.json({ error }, { status: attomRes.status });
    }

    const data = await attomRes.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message || 'Failed to fetch ATTOM data' }, { status: 500 });
  }
} 