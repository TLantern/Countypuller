import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';
import { normalizeAttomParams } from '@/lib/utils';

// Helper to detect web search intent
function hasWebSearchIntent(message: string): boolean {
  const triggers = [
    'search online',
    'look up',
    'find on the web',
    'google',
    'search the web',
    'browse the web',
    'search for',
    'look this up',
    'find information about',
  ];
  const lower = message.toLowerCase();
  return triggers.some(trigger => lower.includes(trigger));
}

// Helper to extract postal code from message (simple US ZIP regex)
function extractPostalCode(message: string): string | null {
  const zipMatch = message.match(/\b\d{5}(?:-\d{4})?\b/);
  return zipMatch ? zipMatch[0] : null;
}

export async function POST(req: NextRequest) {
  const { message, chatHistory } = await req.json();

  console.log("Received message:", message);

  // Helper to fetch property data if needed (stub, replace with real logic if available)
  async function fetchPropertyData(params: any) {
    // You can implement a real lookup here if you have a property DB or API
    // For now, just return an empty object
    return {};
  }

  // 1. Normalize user input for ATTOM API (async)
  const { street, city, state, zip, county } = await normalizeAttomParams(message, fetchPropertyData);
  console.log("Normalized params:", { street, city, state, zip, county });
  const hasAddress = street && city && state && zip;

  // Helper to build query string for ATTOM
  function buildAttomParams() {
    return [
      `street=${encodeURIComponent(street)}`,
      city ? `city=${encodeURIComponent(city)}` : '',
      state ? `state=${encodeURIComponent(state)}` : '',
      zip ? `zip=${encodeURIComponent(zip)}` : '',
      county ? `county=${encodeURIComponent(county)}` : 'county=US'
    ].filter(Boolean).join('&');
  }

  // 2. Query property data from ATTOM API via internal endpoint
  let attomPropertyData = null;
  if (hasAddress) {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://www.clerkcrawler.com/';
    const attomUrl = `${baseUrl}/api/attom/property/detail?${buildAttomParams()}`;
    console.log('ATTOM Request URL:', attomUrl);
    try {
      const attomRes = await fetch(attomUrl);
      const rawText = await attomRes.text();
      console.log('ATTOM Raw Response:', rawText);
      if (attomRes.ok) {
        try {
          attomPropertyData = JSON.parse(rawText);
        } catch (e) {
          attomPropertyData = null;
        }
      }
    } catch (e) {
      console.error('ATTOM Fetch Error:', e);
    }
  }

  console.log("ATTOM Property Data:", attomPropertyData);

  // 3. Query comps from ATTOM API via internal endpoint
  let attomCompsData = null;
  if (hasAddress) {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://www.clerkcrawler.com/';
    const compsUrl = `${baseUrl}/api/attom/salescomps/detail?${buildAttomParams()}`;
    console.log('ATTOM Comps Request URL:', compsUrl);
    try {
      const compsRes = await fetch(compsUrl);
      const compsRawText = await compsRes.text();
      console.log('ATTOM Comps Raw Response:', compsRawText);
      if (compsRes.ok) {
        try {
          attomCompsData = JSON.parse(compsRawText);
        } catch (e) {
          attomCompsData = null;
        }
      }
    } catch (e) {
      console.error('ATTOM Comps Fetch Error:', e);
    }
  }

  console.log("ATTOM Comps Data:", attomCompsData);

  // 4. Query property data from DB (lis pendens filings)
  let propertyData = null;
  if (street) {
    propertyData = await prisma.lis_pendens_filing.findFirst({
      where: { property_address: { contains: street, mode: 'insensitive' } }
    });
  }

  console.log("Lis Pendens Data:", propertyData);

  // 5. Query SerpAPI for Google Search Results
  let webResults = [];
  // If user has web search intent, always search using the full message
  if (hasWebSearchIntent(message) && process.env.SERPAPI_KEY) {
    const serpRes = await fetch(
      `https://serpapi.com/search.json?q=${encodeURIComponent(message)}&engine=google&api_key=${process.env.SERPAPI_KEY}`
    );
    const serpData = await serpRes.json();
    webResults = (serpData.organic_results || []).map((item: any) => ({
      title: item.title,
      url: item.link,
      snippet: item.snippet,
    }));
     } else if (hasAddress && process.env.SERPAPI_KEY) {
       // Fallback: search by address if present
      const addressString = [street, city, state, zip].filter(Boolean).join(', ');
      const serpRes = await fetch(
     `https://serpapi.com/search.json?q=${encodeURIComponent(addressString)}&engine=google&api_key=${process.env.SERPAPI_KEY}`
       );
       const serpData = await serpRes.json();
      webResults = (serpData.organic_results || []).map((item: any) => ({
         title: item.title,
         url: item.link,
      snippet: item.snippet,
    }));
  }

  // 6. Compose system prompt
  const systemPrompt = 'You are a helpful property research assistant who helps real estate investors find more details on properties theyre researching and make better informed decisions.';

  // 7. Compose property/web context
  const contextString = `\nATTOM Property Data:\n${attomPropertyData ? JSON.stringify(attomPropertyData, null, 2) : 'No ATTOM property data found.'}\n\nATTOM Comps Data:\n${attomCompsData ? JSON.stringify(attomCompsData, null, 2) : 'No ATTOM comps data found.'}\n\nLis Pendens Data:\n${propertyData ? JSON.stringify(propertyData, null, 2) : 'No lis pendens data found.'}`;
  const webResultsString = `\n\nWeb Results:\n${webResults.map((r: any) => r.title + ' (' + r.url + '): ' + r.snippet).join('\n')}`;

  let messages = [];
  if (Array.isArray(chatHistory) && chatHistory.length > 0) {
    // Insert system prompt at the start
    messages = [
      { role: 'system', content: systemPrompt + contextString },
      ...chatHistory
    ];
  } else {
    // Fallback: just use system prompt and current message
    messages = [
      { role: 'system', content: systemPrompt + contextString },
      { role: 'user', content: message }
    ];
  }
  
  let reply = 'Sorry, no response.';
  if (process.env.OPENAI_API_KEY) {
    const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages,
        max_tokens: 500,
      }),
    });
    const openaiData = await openaiRes.json();
    reply = openaiData.choices?.[0]?.message?.content || reply;
  }

  console.log("Reply:", reply);

  return NextResponse.json({ reply });
} 