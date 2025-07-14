import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";

export async function POST(req: NextRequest) {
  const timestamp = new Date().toISOString();
  console.log(`🔄 [${timestamp}] SUPPORT CHAT API: Starting support chat request`);
  
  try {
    const session = await getServerSession(authOptions);
    
    if (!session || !session.user) {
      console.log(`❌ [${timestamp}] SUPPORT CHAT API: Authentication failed - no session or user`);
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    console.log(`✅ [${timestamp}] SUPPORT CHAT API: User authenticated - ${session.user.email}`);

    const body = await req.json();
    const { message, conversationHistory, userContext } = body;

    if (!message || message.trim() === '') {
      console.log(`❌ [${timestamp}] SUPPORT CHAT API: Message validation failed - empty message`);
      return NextResponse.json({ error: 'Message is required' }, { status: 400 });
    }

    console.log(`📝 [${timestamp}] SUPPORT CHAT API: Processing message from ${session.user.email}`);
    console.log(`   - Message length: ${message.length} characters`);
    console.log(`   - Conversation history: ${conversationHistory?.length || 0} messages`);

    // Prepare the context for ChatGPT
    const systemPrompt = `You are a helpful support assistant for Clerk Crawler, a property records search and analysis platform. 

About Clerk Crawler:
- It's a web application that helps users search and analyze property records across 200+ counties
- Users can pull records for foreclosures, lis pendens, probate, tax delinquency, and other property-related documents
- The platform includes features like Hot 20 analysis, skip trace, address enrichment, and export capabilities
- Users can filter records by date ranges, property types, and counties
- The system supports multiple user types (LPH, Investor, etc.) with different access levels

Your role:
- Provide helpful, accurate information about using Clerk Crawler
- Help troubleshoot issues with record searches, data exports, or platform features
- Explain how different features work (Hot 20, skip trace, address enrichment, etc.)
- Guide users through common workflows
- Be friendly, professional, and concise
- If you encounter technical issues you can't resolve, suggest the user request human support
- Never make up information about features that don't exist

User context:
- Email: ${userContext?.email || 'Not provided'}
- Name: ${userContext?.name || 'Not provided'}

Remember to be helpful and stay focused on Clerk Crawler support topics.`;

    // Build the conversation for ChatGPT
    const messages = [
      { role: 'system', content: systemPrompt },
      // Add conversation history (limit to last 10 messages to avoid token limits)
      ...conversationHistory.slice(-10).map((msg: any) => ({
        role: msg.role === 'assistant' ? 'assistant' : 'user',
        content: msg.content
      })),
      { role: 'user', content: message }
    ];

    console.log(`🤖 [${timestamp}] SUPPORT CHAT API: Sending request to OpenAI`);

    // Call OpenAI API
    const openaiResponse = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini', // Using gpt-4o-mini for cost efficiency
        messages: messages,
        max_tokens: 500,
        temperature: 0.7,
        presence_penalty: 0.1,
        frequency_penalty: 0.1
      }),
    });

    if (!openaiResponse.ok) {
      const errorData = await openaiResponse.json();
      console.error(`❌ [${timestamp}] SUPPORT CHAT API: OpenAI API error:`, errorData);
      throw new Error(`OpenAI API error: ${errorData.error?.message || 'Unknown error'}`);
    }

    const openaiData = await openaiResponse.json();
    const assistantMessage = openaiData.choices[0]?.message?.content;

    if (!assistantMessage) {
      console.error(`❌ [${timestamp}] SUPPORT CHAT API: No response from OpenAI`);
      throw new Error('No response from OpenAI');
    }

    console.log(`✅ [${timestamp}] SUPPORT CHAT API: Response generated successfully`);
    console.log(`   - Response length: ${assistantMessage.length} characters`);

    return NextResponse.json({ 
      success: true, 
      message: assistantMessage 
    });

  } catch (error: any) {
    console.error(`❌ [${timestamp}] SUPPORT CHAT API: Error occurred during chat processing`);
    console.error(`   - Error type: ${error.constructor.name}`);
    console.error(`   - Error message: ${error.message}`);
    console.error(`   - Full error:`, error);

    // Check if it's an OpenAI API error
    if (error.message.includes('OpenAI API error')) {
      return NextResponse.json(
        { error: 'AI service temporarily unavailable. Please try again or request human support.' }, 
        { status: 503 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to process support request' }, 
      { status: 500 }
    );
  }
} 