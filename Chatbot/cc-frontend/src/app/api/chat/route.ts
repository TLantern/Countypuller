import { NextRequest, NextResponse } from 'next/server';
import prisma from '@/lib/prisma';

export async function POST(req: NextRequest) {
  const { message, chatHistory } = await req.json();

  // 1. Try to extract an address from the message (improve this as needed)
  const addressMatch = message.match(/\d+\s+.+/);
  const address = addressMatch ? addressMatch[0] : null;

  // 2. Query property data from DB
  let propertyData = null;
  if (address) {
    propertyData = await prisma.lis_pendens_filing.findFirst({
      where: { property_address: { contains: address, mode: 'insensitive' } }
    });
  }

  // 3. Query SerpAPI for Google Search Results
  let webResults = [];
  if (address && process.env.SERPAPI_KEY) {
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

  // 4. Compose system prompt
  const systemPrompt = 'You are a helpful property research assistant who helps real estate investors find more details on properties theyre researching and make better informed decisions.';

  // 5. Compose property/web context
  const contextString = `\nProperty Data:\n${propertyData ? JSON.stringify(propertyData, null, 2) : 'No property data found.'}\n\nWeb Results:\n${webResults.map((r: any) => r.title + ' (' + r.url + '): ' + r.snippet).join('\n')}`;

  // 6. Build messages array for OpenAI
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

  // 7. Call OpenAI API
  let reply = 'Sorry, no response.';
  if (process.env.OPENAI_API_KEY) {
    const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4',
        messages,
        max_tokens: 500,
      }),
    });
    const openaiData = await openaiRes.json();
    reply = openaiData.choices?.[0]?.message?.content || reply;
  }

  return NextResponse.json({ reply });
} 