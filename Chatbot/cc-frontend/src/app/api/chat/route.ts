import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';

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

  // 1. Try to extract an address from the message (improve this as needed)
  const addressMatch = message.match(/\d+\s+.+/);
  const address = addressMatch ? addressMatch[0] : null;
  const postalCode = extractPostalCode(message);

  // 2. Query property data from ATTOM API via internal endpoint
  let attomPropertyData = null;
  if (address) {
    try {
      const attomRes = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || ''}/api/attom/property/detail?address1=${encodeURIComponent(address)}${postalCode ? `&postalcode=${postalCode}` : ''}`);
      if (attomRes.ok) {
        attomPropertyData = await attomRes.json();
      }
    } catch (e) {
      // Ignore errors, fallback to DB or SERP
    }
  }

  // 3. Query comps from ATTOM API via internal endpoint
  let attomCompsData = null;
  if (address) {
    try {
      const compsRes = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL || ''}/api/attom/salescomps/detail?address1=${encodeURIComponent(address)}${postalCode ? `&postalcode=${postalCode}` : ''}`);
      if (compsRes.ok) {
        attomCompsData = await compsRes.json();
      }
    } catch (e) {
      // Ignore errors
    }
  }

  // 4. Query property data from DB (lis pendens filings)
  let propertyData = null;
  if (address) {
    propertyData = await prisma.lis_pendens_filing.findFirst({
      where: { property_address: { contains: address, mode: 'insensitive' } }
    });
  }

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
  } else if (address && process.env.SERPAPI_KEY) {
    // Fallback: search by address if present
    const serpRes = await fetch(
      `https://serpapi.com/search.json?q=${encodeURIComponent(address)}&engine=google&api_key=${process.env.SERPAPI_KEY}`
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
  const contextString = `\nATTOM Property Data:\n${attomPropertyData ? JSON.stringify(attomPropertyData, null, 2) : 'No ATTOM property data found.'}\n\nATTOM Comps Data:\n${attomCompsData ? JSON.stringify(attomCompsData, null, 2) : 'No ATTOM comps data found.'}\n\nLis Pendens Data:\n${propertyData ? JSON.stringify(propertyData, null, 2) : 'No lis pendens data found.'}\n\nWeb Results:\n${webResults.map((r: any) => r.title + ' (' + r.url + '): ' + r.snippet).join('\n')}`;

  // 8. Build messages array for OpenAI
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

  // 9. Call OpenAI API
  let reply = 'Sorry, no response.';
  if (process.env.OPENAI_API_KEY) {
    const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o',
        messages,
        max_tokens: 500,
      }),
    });
    const openaiData = await openaiRes.json();
    reply = openaiData.choices?.[0]?.message?.content || reply;
  }

  return NextResponse.json({ reply });
} 