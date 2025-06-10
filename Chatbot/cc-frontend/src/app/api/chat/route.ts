import { NextRequest, NextResponse } from 'next/server';
import { normalizeAttomParams } from '@/lib/utils';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import prisma from '../../../lib/prisma';

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

  // 3. If SERP results are insufficient and we have address, try ATTOM API
  let attomData = null;
  if (!serpResultsSufficient && hasAddress && process.env.ATTOM_API_KEY) {
    const attomParams = buildAttomParams();
    console.log('ATTOM API params:', attomParams);
    
    try {
      const attomRes = await fetch(
        `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail?${attomParams}`,
        {
          headers: {
            'Accept': 'application/json',
            'apikey': process.env.ATTOM_API_KEY,
          },
        }
      );
      
      if (attomRes.ok) {
        attomData = await attomRes.json();
        console.log('ATTOM API response received');
      } else {
        console.log('ATTOM API request failed:', attomRes.status);
      }
    } catch (e) {
      console.error('ATTOM API Error:', e);
    }
  }

  // 4. Prepare context for LLM
  let context = '';
  
  if (webResults.length > 0) {
    context += '\n\nWeb Search Results:\n';
    webResults.slice(0, 5).forEach((result: any, i: number) => {
      context += `${i + 1}. ${result.title}\n${result.snippet}\nURL: ${result.url}\n\n`;
    });
  }
  
  if (attomData && attomData.property && attomData.property.length > 0) {
    context += '\n\nProperty Data:\n';
    const property = attomData.property[0];
    if (property.address) {
      context += `Address: ${property.address.oneLine || 'N/A'}\n`;
    }
    if (property.assessment) {
      context += `Assessed Value: $${property.assessment.assessed?.total || 'N/A'}\n`;
      context += `Market Value: $${property.assessment.market?.mktTtlValue || 'N/A'}\n`;
    }
    if (property.building) {
      context += `Year Built: ${property.building.yearBuilt || 'N/A'}\n`;
      context += `Square Feet: ${property.building.size?.livingSize || 'N/A'}\n`;
    }
  }

  // 5. Call OpenAI/LLM with the context
  try {
    if (!process.env.OPENAI_API_KEY) {
      throw new Error('OPENAI_API_KEY not configured');
    }

    const systemPrompt = `You are a helpful real estate and property information assistant. Use the provided context to answer user questions about properties, real estate, and related topics. If you don't have enough information in the context, say so clearly.`;

    const userPrompt = `User message: "${message}"

Context:${context}

Please provide a helpful response based on the available information.`;

    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-3.5-turbo',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.7,
        max_tokens: 1000,
      }),
    });

    if (!response.ok) {
      throw new Error(`OpenAI API error: ${response.status}`);
    }

    const data = await response.json();
    const aiResponse = data.choices[0]?.message?.content || 'Sorry, I could not generate a response.';

    return NextResponse.json({
      message: aiResponse,
      sources: webResults.slice(0, 3),
      hasPropertyData: !!attomData
    });

  } catch (error) {
    console.error('Chat API Error:', error);
    return NextResponse.json(
      { error: 'Failed to process chat request' },
      { status: 500 }
    );
  }
}