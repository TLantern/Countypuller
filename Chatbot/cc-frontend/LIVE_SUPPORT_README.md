# Live Support System

## Overview
The live support system has been successfully implemented to replace the previous feedback system. Users can now access a ChatGPT-powered support chatbot with the ability to escalate to human support when needed.

## Features

### 🤖 AI-Powered Support
- **ChatGPT Integration**: Uses OpenAI's GPT-4o-mini model for cost-effective, intelligent responses
- **Context-Aware**: Understands Clerk Crawler features and can provide specific guidance
- **Conversation History**: Maintains context throughout the conversation
- **Specialized Knowledge**: Trained on Clerk Crawler features including:
  - Property record searches
  - Hot 20 analysis
  - Skip trace functionality
  - Address enrichment
  - Export capabilities
  - User types and access levels

### 🚨 Human Escalation
- **Automatic Detection**: Recognizes when users request human support
- **Email Notifications**: Sends high-priority emails to safeharbouragent@gmail.com
- **Conversation Context**: Includes full conversation history in escalation emails
- **Visual Indicators**: Shows escalation status in the UI

### 🎨 Modern Interface
- **Clean Design**: Modern chat interface with message bubbles
- **Real-time Updates**: Instant message delivery and typing indicators
- **Responsive Layout**: Works on desktop and mobile devices
- **Accessibility**: Keyboard shortcuts and screen reader support

## How to Access

### From Dashboard
1. Click the blue message icon (💬) in the top-right corner of the dashboard
2. This will navigate you to the live support page at `/live-support`

### Direct Access
- Navigate to `/live-support` in your browser
- Requires authentication (redirects to login if not signed in)

## Usage

### Getting AI Support
1. Type your question in the message box
2. Press Enter or click the send button
3. The AI will respond with helpful information about Clerk Crawler
4. Continue the conversation as needed

### Escalating to Human Support
You can request human support in several ways:
- Type phrases like "I need to speak with a human"
- Ask to "talk to a person" or "speak to someone"
- Use the "Request human support" link at the bottom of the chat
- The system will automatically detect escalation requests

### Keyboard Shortcuts
- **Enter**: Send message
- **Shift + Enter**: New line in message
- **Escape**: Clear current message

## Technical Implementation

### Frontend Components
- **Live Support Page**: `/src/app/live-support/page.tsx`
- **Modern React**: Uses hooks for state management
- **TypeScript**: Full type safety
- **Tailwind CSS**: Responsive styling
- **Lucide Icons**: Modern iconography

### Backend APIs

#### Support Chat API (`/api/support-chat`)
- **Endpoint**: `POST /api/support-chat`
- **Purpose**: Processes user messages and generates AI responses
- **Model**: GPT-4o-mini for cost efficiency
- **Features**:
  - Conversation context maintenance
  - Clerk Crawler specialized knowledge
  - Error handling and fallbacks
  - Rate limiting and token management

#### Support Escalation API (`/api/support-escalation`)
- **Endpoint**: `POST /api/support-escalation`
- **Purpose**: Handles escalation to human support
- **Features**:
  - High-priority email notifications
  - Conversation history inclusion
  - Console logging for immediate visibility
  - SMTP error handling

### Environment Variables Required

```bash
# OpenAI API Key (Required)
OPENAI_API_KEY=your_openai_api_key_here

# Email Configuration (Required for escalation)
EMAIL_USER=your_gmail_address@gmail.com
EMAIL_PASS=your_gmail_app_password
```

## Configuration

### OpenAI Settings
- **Model**: gpt-4o-mini (cost-effective)
- **Max Tokens**: 500 per response
- **Temperature**: 0.7 (balanced creativity)
- **Context Window**: Last 10 messages

### Email Settings
- **Service**: Gmail SMTP
- **Priority**: High priority for escalation emails
- **Recipient**: safeharbouragent@gmail.com

## Monitoring and Logging

### Console Logging
- All support interactions are logged with timestamps
- Escalation requests trigger prominent console alerts
- API errors are logged with full context

### Email Notifications
- Escalation emails include:
  - User details (name, email)
  - Original escalation request
  - Full conversation history
  - Timestamp information
  - Direct contact information

## Security Features

### Authentication
- Requires valid user session
- Redirects to login if unauthenticated
- User context included in all requests

### Data Protection
- No sensitive data stored in chat history
- Temporary conversation storage only
- Secure API key handling

### Rate Limiting
- Built-in OpenAI rate limiting
- Error handling for API limits
- Graceful degradation on failures

## Troubleshooting

### Common Issues

#### "AI service temporarily unavailable"
- Check OPENAI_API_KEY environment variable
- Verify API key has sufficient credits
- Check OpenAI service status

#### Escalation emails not sending
- Verify EMAIL_USER and EMAIL_PASS variables
- Check Gmail app password configuration
- Ensure less secure apps are enabled (if using regular password)

#### Chat not loading
- Check browser console for JavaScript errors
- Verify user is authenticated
- Check network connectivity

### Debug Mode
Enable detailed logging by checking browser console and server logs for:
- API request/response details
- Authentication status
- Error messages and stack traces

## Future Enhancements

### Planned Features
- **Chat History Persistence**: Save conversations to database
- **File Upload Support**: Allow users to upload screenshots or documents
- **Live Chat Integration**: Real-time chat with human support
- **Analytics Dashboard**: Track support metrics and common issues
- **Multi-language Support**: Support for multiple languages
- **Voice Input**: Speech-to-text support
- **Canned Responses**: Quick response templates for common questions

### Integration Opportunities
- **Slack Integration**: Route escalations to Slack channels
- **Zendesk Integration**: Create support tickets automatically
- **Knowledge Base**: Link to documentation and help articles
- **Video Chat**: Integrate with video calling services

## Maintenance

### Regular Tasks
- Monitor OpenAI API usage and costs
- Review escalation emails for common issues
- Update system knowledge base as features change
- Test escalation flow monthly

### Updates
- Keep OpenAI client libraries updated
- Monitor for new model releases
- Update system prompts as features evolve
- Review and optimize token usage

## Support

For technical issues with the live support system itself:
- Check server logs for error details
- Verify environment variables are set correctly
- Test API endpoints directly if needed
- Contact development team for system-level issues

The live support system is designed to provide immediate, intelligent assistance while maintaining the ability to escalate to human support when needed. It replaces the previous feedback system with a more interactive and helpful user experience. 