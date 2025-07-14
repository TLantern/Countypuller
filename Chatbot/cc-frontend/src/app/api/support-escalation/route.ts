import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import nodemailer from 'nodemailer';

export async function POST(req: NextRequest) {
  const timestamp = new Date().toISOString();
  console.log(`🔄 [${timestamp}] SUPPORT ESCALATION API: Starting escalation request`);
  
  try {
    const session = await getServerSession(authOptions);
    
    if (!session || !session.user) {
      console.log(`❌ [${timestamp}] SUPPORT ESCALATION API: Authentication failed - no session or user`);
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    console.log(`✅ [${timestamp}] SUPPORT ESCALATION API: User authenticated - ${session.user.email}`);

    const body = await req.json();
    const { userEmail, userName, originalMessage, conversationHistory } = body;

    console.log(`🚨 [${timestamp}] SUPPORT ESCALATION API: Processing escalation request`);
    console.log(`   - User: ${userEmail} (${userName})`);
    console.log(`   - Original message: ${originalMessage}`);
    console.log(`   - Conversation history: ${conversationHistory?.length || 0} messages`);

    // Create email transporter
    const transporter = nodemailer.createTransport({
      service: 'gmail',
      auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS,
      },
    });

    console.log(`🔧 [${timestamp}] SUPPORT ESCALATION API: Email transporter created`);

    // Format conversation history for email
    const formattedHistory = conversationHistory
      .slice(-10) // Last 10 messages
      .map((msg: any) => {
        const time = new Date(msg.timestamp).toLocaleString();
        const role = msg.role === 'user' ? 'User' : 'Assistant';
        return `[${time}] ${role}: ${msg.content}`;
      })
      .join('\n\n');

    // Email content
    const emailSubject = `🚨 URGENT: Live Support Request - ${userName || userEmail}`;
    const emailBody = `
URGENT: User has requested human support during live chat session.

User Details:
- Name: ${userName || 'Not provided'}
- Email: ${userEmail}
- Timestamp: ${new Date().toLocaleString()}

Original Request:
"${originalMessage}"

Recent Conversation History:
${formattedHistory || 'No conversation history available'}

---
Please respond to this user as soon as possible. They are expecting human support.
You can reach them at: ${userEmail}

This escalation was triggered through the Clerk Crawler live support system.
    `.trim();

    console.log(`📤 [${timestamp}] SUPPORT ESCALATION API: Sending escalation email`);
    console.log(`   - To: safeharbouragent@gmail.com`);
    console.log(`   - Subject: ${emailSubject}`);

    // Send email
    const emailResult = await transporter.sendMail({
      from: process.env.EMAIL_USER,
      to: 'safeharbouragent@gmail.com',
      subject: emailSubject,
      text: emailBody,
      // Add high priority headers
      headers: {
        'X-Priority': '1',
        'X-MSMail-Priority': 'High',
        'Importance': 'high'
      }
    });

    console.log(`✅ [${timestamp}] SUPPORT ESCALATION API: Escalation email sent successfully!`);
    console.log(`   - Message ID: ${emailResult.messageId}`);
    console.log(`   - Response: ${emailResult.response}`);

    // Also log to console for immediate visibility
    console.log(`\n🚨🚨🚨 LIVE SUPPORT ESCALATION 🚨🚨🚨`);
    console.log(`User: ${userName || userEmail} (${userEmail})`);
    console.log(`Time: ${new Date().toLocaleString()}`);
    console.log(`Request: ${originalMessage}`);
    console.log(`🚨🚨🚨 END ESCALATION ALERT 🚨🚨🚨\n`);

    return NextResponse.json({ 
      success: true, 
      message: 'Escalation notification sent successfully' 
    });

  } catch (error: any) {
    console.error(`❌ [${timestamp}] SUPPORT ESCALATION API: Error occurred during escalation`);
    console.error(`   - Error type: ${error.constructor.name}`);
    console.error(`   - Error message: ${error.message}`);
    console.error(`   - Full error:`, error);
    
    // Log specific email-related errors
    if (error.code) {
      console.error(`   - Error code: ${error.code}`);
    }
    if (error.response) {
      console.error(`   - SMTP response: ${error.response}`);
    }
    if (error.command) {
      console.error(`   - SMTP command: ${error.command}`);
    }

    return NextResponse.json(
      { error: 'Failed to send escalation notification' }, 
      { status: 500 }
    );
  }
} 