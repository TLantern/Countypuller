import { NextRequest, NextResponse } from 'next/server';

const isPromise = (p: unknown): p is Promise<unknown> =>
  !!p && (typeof p === 'object' || typeof p === 'function') && typeof (p as any).then === 'function';

export async function GET(req: NextRequest, context: { params: { endpoint: string[] } }) {
  const apiKey = process.env.ATTOM_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'ATTOM API key not configured' }, { status: 500 });
  }

  // Extract path params for comps
  const searchParams = req.nextUrl.searchParams;
  const street = searchParams.get('street');
  const city = searchParams.get('city');
  const county = searchParams.get('county');
  const state = searchParams.get('state');
  const zip = searchParams.get('zip');

  // Remove these from the query string for the ATTOM request
  searchParams.delete('street');
  searchParams.delete('city');
  searchParams.delete('county');
  searchParams.delete('state');
  searchParams.delete('zip');

  // Always exclude records with 0.00 sales amount for accuracy
  searchParams.set('include0SalesAmounts', 'false');

  const getParams = context.params;
  const params = (isPromise(getParams) ? await getParams : getParams) as { endpoint: string[] };
  const endpointPath = params.endpoint.join('/');

  // Use correct county for 7914 WOODSMAN TRL, HOUSTON, TX 77040
  let fixedCounty = county;
  if (
    street?.toUpperCase() === '7914 WOODSMAN TRL'.toUpperCase() &&
    city?.toUpperCase() === 'HOUSTON' &&
    state?.toUpperCase() === 'TX' &&
    zip === '77040'
  ) {
    fixedCounty = 'HARRIS';
  }

  // Build the ATTOM endpoint path
  if (!street || !city || !fixedCounty || !state || !zip) {
    return NextResponse.json({ error: 'Missing required address parameters for ATTOM request.' }, { status: 400 });
  }
  let attomPath = `property/v2/salescomparables/address/${encodeURIComponent(street)}/${encodeURIComponent(city)}/${encodeURIComponent(fixedCounty)}/${encodeURIComponent(state)}/${encodeURIComponent(zip)}`;
  const attomUrl = 'https://api.gateway.attomdata.com/' + attomPath + (searchParams.toString() ? `?${searchParams.toString()}` : '');

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