'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Send, Globe, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Message {
  id: string;
  text: string;
  sender: 'bot' | 'user';
  timestamp: Date;
}

const QUICK_REPLIES = ["Family trip 👨‍👩‍👧‍👧", "Honeymoon 💑", "Adventure tour 🏔️", "Beach holiday 🏖️"];

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notificationCount, setNotificationCount] = useState(1);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initial welcome message
  useEffect(() => {
    if (messages.length === 0) {
      setTimeout(() => {
        const welcome: Message = {
          id: 'welcome',
          text: "Hi! I'm the GeTS AI Assistant. ✈️ Traveling soon? I can help you find tour packages, destinations, itineraries and more. What are you looking for today?",
          sender: 'bot',
          timestamp: new Date(),
        };
        setMessages([welcome]);
      }, 1000);
    }
  }, [messages.length]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleChat = () => {
    setIsOpen(!isOpen);
    if (!isOpen) setNotificationCount(0);
  };

  const handleSend = async (text: string) => {
    if (!text.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      text,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);  // Show typing indicator while pipeline runs
    setError(null);

    // Define botMsgId FIRST so we can exclude it from history
    const botMsgId = (Date.now() + 1).toString();

    // Build clean conversation history — exclude:
    // 1. The welcome message (not a real exchange)
    // 2. The current bot message being streamed (not complete yet)
    // 3. Any empty messages (incomplete streams)
    const conversationHistory = messages
      .filter(m =>
        m.id !== 'welcome' &&         // exclude welcome message
        m.id !== botMsgId &&          // exclude current streaming message
        m.text.trim().length > 0      // exclude empty/incomplete messages
      )
      .map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

    try {
      const response = await fetch('http://localhost:8000/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text,
          conversation_history: conversationHistory,
        }),
      });

      if (!response.ok) throw new Error('Failed to connect');
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let firstToken = true;
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const token = line.slice(6); // Strip "data: " prefix

          if (token === '[DONE]') break;
          if (token.startsWith('[ERROR]')) {
            setError("Sorry, I'm having trouble connecting. Please try again.");
            setIsLoading(false);
            return;
          }

          // Restore newlines that were escaped for SSE transport
          const decodedToken = token.replace(/\\n/g, '\n');
          fullText += decodedToken;

          if (firstToken) {
            // First token arrived — hide typing indicator, show message bubble
            setIsLoading(false);
            firstToken = false;
            setMessages(prev => [
              ...prev,
              {
                id: botMsgId,
                text: decodedToken,
                sender: 'bot',
                timestamp: new Date(),
              },
            ]);
          } else {
            // Subsequent tokens — append to existing bot message
            setMessages(prev =>
              prev.map(m =>
                m.id === botMsgId
                  ? { ...m, text: m.text + decodedToken }
                  : m
              )
            );
          }
        }
      }

    } catch (err) {
      setError("Sorry, I'm having trouble connecting. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-jakarta">
      {/* Popout Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20, transformOrigin: 'bottom right' }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="absolute bottom-20 right-0 w-[380px] h-[580px] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200"
          >
            {/* Header */}
            <div className="bg-gets-red p-4 flex items-center justify-between text-white shadow-md">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                  <Globe size={18} />
                </div>
                <div>
                  <h3 className="font-bold text-sm">GeTS AI Assistant</h3>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                    <span className="text-[10px] text-white/80 font-medium">Online</span>
                  </div>
                </div>
              </div>
              <button
                onClick={toggleChat}
                className="hover:bg-white/10 p-1.5 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scrollbar bg-[#f8fafc]">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[80%] flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`px-4 py-2.5 rounded-2xl text-[14px] leading-relaxed shadow-sm ${msg.sender === 'user'
                          ? 'bg-gets-red text-white rounded-tr-none'
                          : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
                        }`}
                    >
                      {msg.text}
                    </div>
                    <span className="text-[10px] text-slate-400 mt-1.5 uppercase font-medium tracking-wider">
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-slate-100 px-4 py-3 rounded-2xl rounded-tl-none shadow-sm flex gap-1.5 items-center">
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0s' }} />
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.2s' }} />
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.4s' }} />
                  </div>
                </div>
              )}

              {error && (
                <div className="flex justify-center">
                  <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-xs flex items-center gap-2 border border-red-100">
                    <AlertCircle size={14} />
                    {error}
                  </div>
                </div>
              )}

              {messages.length === 1 && !isLoading && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {QUICK_REPLIES.map((reply) => (
                    <button
                      key={reply}
                      onClick={() => handleSend(reply)}
                      className="px-3 py-1.5 rounded-full border border-gets-red text-gets-red text-[13px] font-medium hover:bg-gets-red hover:text-white transition-all active:scale-95 bg-white shadow-sm"
                    >
                      {reply}
                    </button>
                  ))}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-white border-t border-slate-100">
              <div className="relative flex items-center gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
                  placeholder="Type your travel query..."
                  className="flex-1 bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-gets-red/20 outline-none text-slate-700 placeholder:text-slate-400 transition-all"
                />
                <button
                  onClick={() => handleSend(input)}
                  disabled={!input.trim() || isLoading}
                  className="bg-gets-red text-white p-3 rounded-xl hover:bg-[#b30000] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-red-900/10"
                >
                  <Send size={18} />
                </button>
              </div>
              <p className="text-center text-[10px] text-slate-400 mt-3 font-medium uppercase tracking-widest">
                Powered by GeTS AI
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Bubble */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={toggleChat}
        className="relative w-14 h-14 bg-gets-red rounded-full flex items-center justify-center text-white shadow-xl hover:shadow-2xl transition-all border-4 border-white/10"
      >
        {isOpen ? <X size={26} /> : <MessageCircle size={26} fill="white" />}

        {notificationCount > 0 && !isOpen && (
          <span className="absolute -top-1 -right-1 w-6 h-6 bg-red-600 text-white text-[11px] font-bold rounded-full flex items-center justify-center border-2 border-white animate-bounce">
            {notificationCount}
          </span>
        )}
      </motion.button>
    </div>
  );
}