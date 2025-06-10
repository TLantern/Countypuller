import React, { useState, useRef, useEffect } from 'react';
import { MessageList } from 'react-chat-elements';
import 'react-chat-elements/dist/main.css';

// Bouncing dots loading indicator
const BouncingDots = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 40, margin: '12px 0' }}>
    <style>{`
      .dot {
        width: 12px;
        height: 12px;
        margin: 0 6px;
        background: #222;
        border-radius: 50%;
        display: inline-block;
        animation: bounce 1.2s infinite;
      }
      .dot:nth-child(2) { animation-delay: 0.2s; }
      .dot:nth-child(3) { animation-delay: 0.4s; }
      @keyframes bounce {
        0%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-16px); }
      }
    `}</style>
    <span className="dot" />
    <span className="dot" />
    <span className="dot" />
  </div>
);

// Helper to convert URLs to clickable 'link' text
function linkify(text: string | undefined | null) {
  if (!text || typeof text !== 'string') {
    return '';
  }
  const urlRegex = /(https?:\/\/[^\s)]+)/g;
  return text.replace(urlRegex, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">link</a>`);
}

interface ChatBoxProps {
  messages: any[];
  setMessages: React.Dispatch<React.SetStateAction<any[]>>;
  onNewChat?: () => void;
  externalMessage?: string | null;
  onExternalMessageHandled?: () => void;
}

function useIsMobile() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 600px)').matches;
}

const ChatBox = ({ messages, setMessages, onNewChat, externalMessage, onExternalMessageHandled }: ChatBoxProps) => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messageListRef = useRef(null);
  const messageListEndRef = useRef<HTMLDivElement | null>(null);
  const [showStartNotice, setShowStartNotice] = useState(true);
  const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 600px)').matches;

  // Property-related queries that users can click
  const suggestedQueries = [
    "Search for properties by address",
    "Find liens on a specific property", 
    "Check property ownership history",
    "Get property tax information",
    "Look up recent property transfers",
    "Find foreclosure records",
    "Search by property owner name",
    "Get property assessment details"
  ];

  // Handle clicking on a suggested query
  const handleQueryClick = (query: string) => {
    setInput(query);
    setShowStartNotice(false);
  };

  // Auto-scroll to latest message when messages change
  useEffect(() => {
    if (messageListEndRef.current) {
      messageListEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  // Show suggested queries when chat is opened/reopened
  useEffect(() => {
    setShowStartNotice(true);
    const timer = setTimeout(() => setShowStartNotice(false), 10000); // Show for 10 seconds
    return () => clearTimeout(timer);
  }, []); // Only on mount (chat open/reopen)

  // Add external message as a box to chat
  React.useEffect(() => {
    if (externalMessage) {
      setMessages(msgs => [
        ...msgs,
        { position: 'right', type: 'box', text: externalMessage }
      ]);
      if (onExternalMessageHandled) onExternalMessageHandled();
    }
  }, [externalMessage, onExternalMessageHandled, setMessages]);

  // Send message with chat memory
  const sendMessage = async () => {
    if (!input.trim()) return;
    const newMessages = [...messages, { position: 'right', type: 'text', text: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    try {
      console.log('Sending message:', input);
      // Prepare chat history for backend (user/bot roles)
      const chatHistory = newMessages.map(msg => ({
        role: msg.position === 'right' ? 'user' : 'assistant',
        content: msg.text
      }));
      console.log('Chat history:', chatHistory);
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, chatHistory }),
      });
      console.log('Response status:', res.status);
      console.log('Response ok:', res.ok);
      const data = await res.json();
      console.log('Response data:', data);
      if (data.message) {
        console.log('Adding bot message to chat:', data.message);
        setMessages(msgs => [...msgs, { position: 'left', type: 'text', text: data.message }]);
      } else {
        console.error('No message field in response:', data);
        setMessages(msgs => [...msgs, { position: 'left', type: 'text', text: 'Error: No response message received.' }]);
      }
    } catch (e) {
      console.error('Chat error:', e);
      setMessages(msgs => [...msgs, { position: 'left', type: 'text', text: 'Error: Could not get response.' }]);
    }
    setLoading(false);
  };

  // Custom message rendering for clickable links in bot messages
  const renderMessage = (msg: any, idx: number) => {
    // Safety check for message structure
    if (!msg) {
      return null;
    }

    const messageText = msg.text || '';

    if (msg.type === 'box') {
      return (
        <div key={idx} style={{ textAlign: 'right', margin: '6px 0' }}>
          <span style={{ background: '#1976d2', color: '#fff', padding: '8px 18px', borderRadius: 12, fontWeight: 700, fontSize: 18, display: 'inline-block', letterSpacing: 2, boxShadow: '0 2px 8px rgba(25,118,210,0.08)' }}>{messageText}</span>
        </div>
      );
    }
    if (msg.position === 'left') {
      // Bot message: linkify URLs and render as HTML
      return (
        <div key={idx} style={{ textAlign: 'left', margin: '6px 0' }}>
          <span
            style={{ background: '#d1d5db', color: '#111', padding: '6px 12px', borderRadius: 16, display: 'inline-block' }}
            dangerouslySetInnerHTML={{ __html: linkify(messageText) }}
          />
        </div>
      );
    } else {
      // User message: plain text
      return (
        <div key={idx} style={{ textAlign: 'right', margin: '6px 0' }}>
          <span style={{ background: '#b3e5fc', color: '#111', padding: '6px 12px', borderRadius: 16, display: 'inline-block' }}>{messageText}</span>
        </div>
      );
    }
  };

  return (
    <div style={{
      maxWidth: isMobile ? '100%' : 900,
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: '#fff',
      borderRadius: 12,
      boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
      padding: 0,
    }} className="responsive-full-width responsive-padding">
      <div style={{
        display: 'flex',
        alignItems: 'center',
        borderTopLeftRadius: 12,
        borderTopRightRadius: 12,
        padding: isMobile ? 16 : 32,
        paddingBottom: isMobile ? 8 : 16,
        borderBottom: '1px solid #eee',
        background: '#222',
        flexWrap: 'wrap',
        flexDirection: isMobile ? 'column' : 'row',
      }} className="responsive-padding">
        <button
          onClick={onNewChat}
          style={{
            background: '#1976d2',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            marginRight: isMobile ? 0 : 16,
            marginBottom: isMobile ? 8 : 0,
            width: 40,
            height: 40,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="New Chat"
        >
          {/* White plus sign */}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
        <h2 style={{ flex: 1, textAlign: 'center', fontWeight: 600, fontSize: isMobile ? 18 : 26, marginBottom: 0, color: '#fff' }} className="responsive-font-lg">What can I help with?</h2>
      </div>
      <div style={{
        flex: 1,
        minHeight: 0,
        maxHeight: '100%',
        overflowY: 'auto',
        background: '#fff',
        padding: isMobile ? 12 : 24,
        borderBottomLeftRadius: 12,
        borderBottomRightRadius: 12,
      }} className="responsive-padding">
        {showStartNotice && (
          <div style={{ textAlign: 'center', color: '#1976d2', fontWeight: 600, marginBottom: 12 }}>
            <div style={{ marginBottom: 12, fontSize: 16, color: '#666' }}>
              Try asking about:
            </div>
            <div style={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              gap: 8, 
              justifyContent: 'center',
              alignItems: 'center'
            }}>
              {suggestedQueries.map((query, index) => (
                <button
                  key={index}
                  onClick={() => handleQueryClick(query)}
                  style={{
                    background: '#f0f9ff',
                    border: '1px solid #1976d2',
                    borderRadius: 20,
                    padding: '6px 12px',
                    fontSize: 13,
                    color: '#1976d2',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    margin: 2,
                    fontWeight: 500
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#1976d2';
                    e.currentTarget.style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#f0f9ff';
                    e.currentTarget.style.color = '#1976d2';
                  }}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map(renderMessage)}
        {loading && <BouncingDots />}
        <div ref={messageListEndRef} />
      </div>
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        alignItems: 'center',
        background: '#222',
        borderRadius: 8,
        margin: isMobile ? 12 : 24,
        marginTop: 0,
        padding: isMobile ? 4 : 8,
        flexWrap: 'wrap',
        gap: isMobile ? 8 : 0,
      }} className="responsive-padding responsive-flex-col">
        <input
          type="text"
          placeholder="Ask about a property..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => { if (e.key === 'Enter') sendMessage(); }}
          style={{
            flex: 1,
            width: '100%',
            background: 'transparent',
            border: 'none',
            color: '#fff',
            fontSize: isMobile ? 16 : 18,
            padding: isMobile ? '8px 10px' : '12px 16px',
            outline: 'none',
            marginBottom: isMobile ? 8 : 0,
          }}
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          style={{
            marginLeft: isMobile ? 0 : 12,
            width: isMobile ? '100%' : 44,
            height: 44,
            borderRadius: '50%',
            background: '#1976d2',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !input.trim() ? 0.6 : 1,
            transition: 'background 0.2s',
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
        </button>
      </div>
    </div>
  );
};

export default ChatBox; 