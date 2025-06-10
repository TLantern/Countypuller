import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "../auth/[...nextauth]/authOptions";
import nodemailer from 'nodemailer';

export async function POST(req: NextRequest) {
  const timestamp = new Date().toISOString();
  console.log(`🔄 [${timestamp}] FEEDBACK API: Starting feedback submission process`);
  
  try {
    const session = await getServerSession(authOptions);
    
    if (!session || !session.user) {
      console.log(`❌ [${timestamp}] FEEDBACK API: Authentication failed - no session or user`);
      return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    }

    console.log(`✅ [${timestamp}] FEEDBACK API: User authenticated - ${session.user.email}`);

    const body = await req.json();
    const { rating, feedback } = body;

    console.log(`📝 [${timestamp}] FEEDBACK API: Received feedback from ${session.user.email}`);
    console.log(`   - Rating: ${rating ? `${rating}/5 stars` : 'No rating'}`);
    console.log(`   - Feedback length: ${feedback?.length || 0} characters`);

    if (!feedback || feedback.trim() === '') {
      console.log(`❌ [${timestamp}] FEEDBACK API: Feedback validation failed - empty feedback`);
      return NextResponse.json({ error: 'Feedback is required' }, { status: 400 });
    }

    console.log(`📧 [${timestamp}] FEEDBACK API: Preparing to send email to safeharbouragent@gmail.com`);

    // Create email transporter
    const transporter = nodemailer.createTransport({
      service: 'gmail',
      auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS,
      },
    });

    console.log(`🔧 [${timestamp}] FEEDBACK API: Email transporter created with user: ${process.env.EMAIL_USER}`);

    // Email content
    const emailSubject = `User Feedback - ${rating ? `${rating}/5 stars` : 'No rating'}`;
    const emailBody = `
New feedback received from user:

User: ${session.user.email}
Rating: ${rating ? `${rating}/5 stars` : 'No rating provided'}
Timestamp: ${new Date().toLocaleString()}

Feedback:
${feedback}

---
This feedback was submitted through the Clerk Crawler dashboard.
    `.trim();

    console.log(`📤 [${timestamp}] FEEDBACK API: Sending email...`);
    console.log(`   - To: safeharbouragent@gmail.com`);
    console.log(`   - Subject: ${emailSubject}`);

    // Send email
    const emailResult = await transporter.sendMail({
      from: process.env.EMAIL_USER,
      to: 'safeharbouragent@gmail.com',
      subject: emailSubject,
      text: emailBody,
    });

    console.log(`✅ [${timestamp}] FEEDBACK API: Email sent successfully!`);
    console.log(`   - Message ID: ${emailResult.messageId}`);
    console.log(`   - Response: ${emailResult.response}`);

    return NextResponse.json({ 
      success: true, 
      message: 'Feedback submitted successfully' 
    });

  } catch (error: any) {
    console.error(`❌ [${timestamp}] FEEDBACK API: Error occurred during feedback submission`);
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
      { error: 'Failed to submit feedback' }, 
      { status: 500 }
    );
  }
} 