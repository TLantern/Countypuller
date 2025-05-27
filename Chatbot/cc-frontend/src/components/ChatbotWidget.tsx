"use client";

import React, { useState, useEffect } from 'react';
import ChatBox from './ChatBox';

const CHAT_HISTORY_KEY = 'chatbot_messages';

const ChatbotWidget = () => {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);

  // Load chat history from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(CHAT_HISTORY_KEY);
    if (saved) {
      setMessages(JSON.parse(saved));
    }
  }, []);

  // Save chat history to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messages));
  }, [messages]);

  // Handler to clear chat history
  const handleNewChat = () => {
    setMessages([]);
  };

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 1000,
        transition: 'width 0.3s, height 0.3s',
        width: expanded ? 400 : 88,
        height: expanded ? 600 : 40,
        borderRadius: expanded ? 16 : 20,
        background: '#111',
        boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
        overflow: 'hidden',
        cursor: expanded ? 'default' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      {expanded ? (
        <div style={{ width: '100%', height: '100%', position: 'relative' }}>
          <ChatBox
            messages={messages}
            setMessages={setMessages}
            onNewChat={handleNewChat}
          />
        </div>
      ) : (
        <div
          style={{
            width: '80%',
            height: 16,
            border: '2px solid #888',
            borderRadius: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 600,
            fontSize: 18,
            background: '#111',
          }}
        >
          {/* Chatbot minimized bar */}
        </div>
      )}
    </div>
  );
};

export default ChatbotWidget; 