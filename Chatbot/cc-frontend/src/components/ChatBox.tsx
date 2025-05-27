import React, { useState, useRef } from 'react';
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
function linkify(text: string) {
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

const ChatBox = ({ messages, setMessages, onNewChat, externalMessage, onExternalMessageHandled }: ChatBoxProps) => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messageListRef = useRef(null);

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
      // Prepare chat history for backend (user/bot roles)
      const chatHistory = newMessages.map(msg => ({
        role: msg.position === 'right' ? 'user' : 'assistant',
        content: msg.text
      }));
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, chatHistory }),
      });
      const data = await res.json();
      setMessages(msgs => [...msgs, { position: 'left', type: 'text', text: data.reply }]);
    } catch (e) {
      setMessages(msgs => [...msgs, { position: 'left', type: 'text', text: 'Error: Could not get response.' }]);
    }
    setLoading(false);
  };

  // Custom message rendering for clickable links in bot messages
  const renderMessage = (msg: any, idx: number) => {
    if (msg.type === 'box') {
      return (
        <div key={idx} style={{ textAlign: 'right', margin: '6px 0' }}>
          <span style={{ background: '#1976d2', color: '#fff', padding: '8px 18px', borderRadius: 12, fontWeight: 700, fontSize: 18, display: 'inline-block', letterSpacing: 2, boxShadow: '0 2px 8px rgba(25,118,210,0.08)' }}>{msg.text}</span>
        </div>
      );
    }
    if (msg.position === 'left') {
      // Bot message: linkify URLs and render as HTML
      return (
        <div key={idx} style={{ textAlign: 'left', margin: '6px 0' }}>
          <span
            style={{ background: '#d1d5db', color: '#111', padding: '6px 12px', borderRadius: 16, display: 'inline-block' }}
            dangerouslySetInnerHTML={{ __html: linkify(msg.text) }}
          />
        </div>
      );
    } else {
      // User message: plain text
      return (
        <div key={idx} style={{ textAlign: 'right', margin: '6px 0' }}>
          <span style={{ background: '#b3e5fc', color: '#111', padding: '6px 12px', borderRadius: 16, display: 'inline-block' }}>{msg.text}</span>
        </div>
      );
    }
  };

  return (
    <div style={{
      maxWidth: 900,
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: '#fff',
      borderRadius: 12,
      boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
      padding: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        borderTopLeftRadius: 12,
        borderTopRightRadius: 12,
        padding: 32,
        paddingBottom: 16,
        borderBottom: '1px solid #eee',
        background: '#222',
      }}>
        <button
          onClick={onNewChat}
          style={{
            background: '#1976d2',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            marginRight: 16,
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
        <h2 style={{ flex: 1, textAlign: 'center', fontWeight: 600, fontSize: 26, marginBottom: 0, color: '#fff' }}>What can I help with?</h2>
      </div>
      <div style={{
        flex: 1,
        minHeight: 0,
        maxHeight: '100%',
        overflowY: 'auto',
        background: '#fff',
        padding: 24,
        borderBottomLeftRadius: 12,
        borderBottomRightRadius: 12,
      }}>
        {messages.map(renderMessage)}
        {loading && <BouncingDots />}
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#222',
        borderRadius: 8,
        margin: 24,
        marginTop: 0,
        padding: 8,
      }}>
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
            fontSize: 18,
            padding: '12px 16px',
            outline: 'none',
          }}
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          style={{
            marginLeft: 12,
            width: 44,
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