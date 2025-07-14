'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Send, Bot, User, AlertCircle, Phone, MessageSquare, UserCheck } from 'lucide-react';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: Date;
  isEscalated?: boolean;
}

// Declare Freshworks widget types
declare global {
  interface Window {
    FreshworksWidget?: any;
  }
}

export default function LiveSupportPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isEscalated, setIsEscalated] = useState(false);
  const [escalationRequested, setEscalationRequested] = useState(false);
  const [freshworksLoaded, setFreshworksLoaded] = useState(false);
  const [showFreshworks, setShowFreshworks] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load Freshworks widget
  useEffect(() => {
    const loadFreshworksWidget = () => {
      // Remove existing script if present
      const existingScript = document.getElementById('freshworks-widget');
      if (existingScript) {
        existingScript.remove();
      }

      // Create and load Freshworks script
      const script = document.createElement('script');
      script.id = 'freshworks-widget';
      script.src = '//fw-cdn.com/13646884/5677047.js';
      script.setAttribute('chat', 'true');
      script.onload = () => {
        console.log('✅ Freshworks widget loaded successfully');
        setFreshworksLoaded(true);
        
        // Configure widget once loaded
        if (window.FreshworksWidget) {
          window.FreshworksWidget('hide', 'launcher');
          
          // Set user properties if available
          if (session?.user) {
            window.FreshworksWidget('identify', 'user', {
              firstName: session.user.name?.split(' ')[0] || '',
              lastName: session.user.name?.split(' ').slice(1).join(' ') || '',
              email: session.user.email || '',
              properties: {
                platform: 'Clerk Crawler',
                userType: 'Dashboard User'
              }
            });
          }
        }
      };
      script.onerror = () => {
        console.error('❌ Failed to load Freshworks widget');
      };
      
      document.head.appendChild(script);
    };

    if (session?.user && !freshworksLoaded) {
      loadFreshworksWidget();
    }

    // Cleanup on unmount
    return () => {
      const script = document.getElementById('freshworks-widget');
      if (script) {
        script.remove();
      }
    };
  }, [session, freshworksLoaded]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login');
    }
  }, [status, router]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize with welcome message
  useEffect(() => {
    if (session?.user) {
      const welcomeMessage: Message = {
        id: 'welcome',
        content: `Hi ${session.user.name || session.user.email}! I'm your AI support assistant. I can help you with questions about Clerk Crawler, property records, troubleshooting, and more. If you need to speak with a human agent, just click the "Connect to Agent" button below.`,
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages([welcomeMessage]);
    }
  }, [session]);

  const handleConnectToAgent = () => {
    if (window.FreshworksWidget && freshworksLoaded) {
      // Show the Freshworks widget
      window.FreshworksWidget('show', 'launcher');
      window.FreshworksWidget('open');
      
      // Add a message to current chat indicating handoff
      const handoffMessage: Message = {
        id: Date.now().toString() + '_handoff',
        content: `I'm connecting you to a human agent now. The Freshworks chat window should appear. You can continue our conversation here or use the agent chat - both options are available to help you!`,
        role: 'assistant',
        timestamp: new Date(),
        isEscalated: true
      };
      setMessages(prev => [...prev, handoffMessage]);
      setShowFreshworks(true);
      setEscalationRequested(true);
      
      // Send escalation notification (keeping existing email system)
      fetch('/api/support-escalation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userEmail: session?.user?.email,
          userName: session?.user?.name,
          originalMessage: 'User requested connection to human agent via Freshworks',
          conversationHistory: messages
        }),
      }).catch(error => console.error('Failed to send escalation notification:', error));
      
    } else {
      // Fallback to email escalation if Freshworks fails
      handleEmailEscalation();
    }
  };

  const handleEmailEscalation = async () => {
    setEscalationRequested(true);
    const escalationMessage: Message = {
      id: Date.now().toString() + '_escalation',
      content: `I understand you'd like to speak with a human. I've notified our support team and they'll be in touch shortly via email. In the meantime, I'm still here to help with any questions you might have.`,
      role: 'assistant',
      timestamp: new Date(),
      isEscalated: true
    };
    setMessages(prev => [...prev, escalationMessage]);
    
    // Send escalation notification
    try {
      await fetch('/api/support-escalation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userEmail: session?.user?.email,
          userName: session?.user?.name,
          originalMessage: 'User requested human support (Freshworks fallback)',
          conversationHistory: messages
        }),
      });
    } catch (error) {
      console.error('Failed to send escalation notification:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputMessage,
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Check if user is requesting escalation
      const escalationKeywords = ['human', 'person', 'real support', 'escalate', 'speak to someone', 'talk to human', 'representative', 'agent'];
      const isEscalationRequest = escalationKeywords.some(keyword => 
        inputMessage.toLowerCase().includes(keyword)
      );

      if (isEscalationRequest && !escalationRequested) {
        handleConnectToAgent();
        setIsLoading(false);
        return;
      }

      // Send to ChatGPT for regular support
      const response = await fetch('/api/support-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          conversationHistory: messages,
          userContext: {
            email: session?.user?.email,
            name: session?.user?.name
          }
        }),
      });

      const data = await response.json();

      if (data.success) {
        const assistantMessage: Message = {
          id: Date.now().toString() + '_assistant',
          content: data.message,
          role: 'assistant',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error(data.error || 'Failed to get response');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: Date.now().toString() + '_error',
        content: 'I apologize, but I\'m having trouble responding right now. Please try again in a moment, or you can connect to a human agent for immediate assistance.',
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-purple-800 to-indigo-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-300 mx-auto mb-4"></div>
          <p className="text-white">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-purple-800 to-indigo-900">
      {/* Header */}
      <div className="bg-white/10 backdrop-blur-sm shadow-sm border-b border-white/20">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.back()}
                className="flex items-center gap-2 text-white hover:bg-white/20"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
              <div className="flex items-center gap-2">
                <MessageSquare className="w-6 h-6 text-purple-300" />
                <h1 className="text-xl font-semibold text-white">Live Support</h1>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {escalationRequested && (
                <div className="flex items-center gap-2 bg-orange-500/20 text-orange-200 px-3 py-1 rounded-full text-sm border border-orange-400/30">
                  <AlertCircle className="w-4 h-4" />
                  Agent connected
                </div>
              )}
              
              {freshworksLoaded && (
                <div className="flex items-center gap-2 bg-green-500/20 text-green-200 px-3 py-1 rounded-full text-sm border border-green-400/30">
                  <UserCheck className="w-4 h-4" />
                  Live chat ready
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Chat Container */}
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Card className="h-[600px] flex flex-col bg-white/95 backdrop-blur-sm shadow-2xl border-0">
          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-black shadow-lg'
                      : message.isEscalated
                      ? 'bg-gradient-to-r from-orange-100 to-orange-50 text-orange-900 border border-orange-200 shadow-sm'
                      : 'bg-gradient-to-r from-gray-50 to-gray-100 text-gray-900 shadow-sm'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {message.role === 'assistant' && (
                      <Bot className={`w-4 h-4 mt-1 flex-shrink-0 ${
                        message.isEscalated ? 'text-orange-600' : 'text-gray-600'
                      }`} />
                    )}
                    {message.role === 'user' && (
                      <User className="w-4 h-4 mt-1 flex-shrink-0 text-purple-200" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      <p className={`text-xs mt-1 ${
                        message.role === 'user' ? 'text-purple-200' : 'text-gray-500'
                      }`}>
                        {formatTime(message.timestamp)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-4 py-2 max-w-[70%]">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-gray-600" />
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t p-4">
            <div className="flex gap-2 mb-3">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message here..."
                className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-black"
                rows={1}
                disabled={isLoading}
              />
              <Button
                onClick={handleSendMessage}
                disabled={isLoading || !inputMessage.trim()}
                className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white px-4 py-2 shadow-lg"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
            
            {/* Connect to Agent Button */}
            <div className="flex items-center justify-center mb-2">
              <Button
                onClick={handleConnectToAgent}
                disabled={!freshworksLoaded}
                className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white px-6 py-2 shadow-lg flex items-center gap-2"
              >
                <UserCheck className="w-4 h-4" />
                {freshworksLoaded ? 'Connect to Human Agent' : 'Loading agent chat...'}
              </Button>
            </div>
            
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Press Enter to send, Shift+Enter for new line</span>
              <div className="flex items-center gap-4">
                <span>AI powered by ChatGPT</span>
                <span>•</span>
                <span>Live chat by Freshworks</span>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
} 