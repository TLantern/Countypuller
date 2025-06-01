import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';
import { normalizeAttomParams } from '@/lib/utils';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";

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

// Helper to evaluate if SERP results are sufficient
function areSerpResultsSufficient(webResults: any[], hasWebSearchIntent: boolean): boolean {
  // If user explicitly requested web search, accept any results
  if (hasWebSearchIntent && webResults.length > 0) {
    return true;
  }
  
  // For property-related queries, check if we have enough relevant results
  if (webResults.length >= 3) {
    // Check if results contain property-related terms
    const propertyTerms = ['property', 'real estate', 'home', 'house', 'address', 'zillow', 'realtor', 'mls'];
    const relevantResults = webResults.filter(result => {
      const text = (result.title + ' ' + result.snippet).toLowerCase();
      return propertyTerms.some(term => text.includes(term));
    });
    
    return relevantResults.length >= 2;
  }
  
  return false;
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

  // 1. Normalize user input for potential ATTOM API use later
  const { street, city, state, zip, county } = await normalizeAttomParams(message, fetchPropertyData);
  console.log("Normalized params:", { street, city, state, zip, county });
  const hasAddress = street && city && state && zip;

  // 2. FIRST: Try web search with SERP API
  let webResults = [];
  let serpResultsSufficient = false;
  
  if (process.env.SERPAPI_KEY) {
    let searchQuery = message;
    
    // If we have address info but no explicit web search intent, search by address
    if (!hasWebSearchIntent(message) && hasAddress) {
      searchQuery = [street, city, state, zip].filter(Boolean).join(', ');
    }
    
    console.log('SERP Search Query:', searchQuery);
    
    try {
      const serpRes = await fetch(
        `https://serpapi.com/search.json?q=${encodeURIComponent(searchQuery)}&engine=google&api_key=${process.env.SERPAPI_KEY}`
      );
      const serpData = await serpRes.json();
      webResults = (serpData.organic_results || []).map((item: any) => ({
        title: item.title,
        url: item.link,
        snippet: item.snippet,
      }));
      
      console.log(`SERP returned ${webResults.length} results`);
      serpResultsSufficient = areSerpResultsSufficient(webResults, hasWebSearchIntent(message));
      console.log('SERP results sufficient:', serpResultsSufficient);
    } catch (e) {
      console.error('SERP Fetch Error:', e);
    }
  }

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

  // 3. Only query ATTOM data if SERP results aren't sufficient AND we have address info
  let attomPropertyData = null;
  let attomCompsData = null;
  
  if (!serpResultsSufficient && hasAddress) {
    console.log('SERP results insufficient, querying ATTOM data...');
    
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://www.clerkcrawler.com/';
    
    // Query property data from ATTOM API
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

    // Query comps from ATTOM API
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
  } else if (serpResultsSufficient) {
    console.log('SERP results sufficient, skipping ATTOM queries');
  } else {
    console.log('No address found and SERP results insufficient, skipping ATTOM queries');
  }

  console.log("ATTOM Property Data:", attomPropertyData);
  console.log("ATTOM Comps Data:", attomCompsData);

  // 4. Query property data from DB (lis pendens filings) - always do this if we have street info
  let propertyData = null;
  const session = await getServerSession(authOptions);
  const userId = (session?.user as any)?.id;
  if (street && userId) {
    propertyData = await prisma.lis_pendens_filing.findFirst({
      where: { property_address: { contains: street, mode: 'insensitive' }, userId },
    });
  }

  console.log("Lis Pendens Data:", propertyData);

  // 5. Compose system prompt
  const systemPrompt = 'You are a helpful property research assistant who helps real estate investors find more details on properties theyre researching and make better informed decisions.';

  // 6. Compose context based on what data we have
  let contextString = '';
  
  if (serpResultsSufficient) {
    contextString = `\nWeb Search Results (Primary Source):\n${webResults.map((r: any) => r.title + ' (' + r.url + '): ' + r.snippet).join('\n')}`;
  } else {
    contextString = `\nATTOM Property Data:\n${attomPropertyData ? JSON.stringify(attomPropertyData, null, 2) : 'No ATTOM property data found.'}\n\nATTOM Comps Data:\n${attomCompsData ? JSON.stringify(attomCompsData, null, 2) : 'No ATTOM comps data found.'}`;
    
    if (webResults.length > 0) {
      contextString += `\n\nSupplementary Web Results:\n${webResults.map((r: any) => r.title + ' (' + r.url + '): ' + r.snippet).join('\n')}`;
    }
  }
  
  // Always include lis pendens data if available
  if (propertyData) {
    contextString += `\n\nLis Pendens Data:\n${JSON.stringify(propertyData, null, 2)}`;
  }

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