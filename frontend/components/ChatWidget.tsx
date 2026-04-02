'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Send, Globe, AlertCircle, Phone, PhoneCall, Mail } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ItineraryCard, { ItineraryCardData } from './ItineraryCard';

interface Message {
  id: string;
  text: string;
  sender: 'bot' | 'user';
  timestamp: Date;
}

const QUICK_REPLIES = [
  "A romantic trip 🏰",
  "For a family trip 👨‍👩‍👧",
  "For a trip with my friends 👥",
  "For a solo trip 🧳",
  "Group Tour 🚢",
];

function BotAvatar() {
  return (
    <div className="w-8 h-8 rounded-full bg-[#CC0000] flex items-center justify-center flex-shrink-0 mt-0.5">
      <Globe size={15} className="text-white" />
    </div>
  );
}

function formatTimestamp(date: Date): string {
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const timeStr = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return isToday ? `Today at ${timeStr}` : timeStr;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notificationCount, setNotificationCount] = useState(1);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Only attempt to parse the card once the full delimiters have arrived
  function parseItineraryCard(text: string): { cardData: ItineraryCardData | null; cleanText: string } {
    if (!text.includes('<<<ITINERARY_CARD>>>') || !text.includes('<<<END_ITINERARY_CARD>>>')) {
      return { cardData: null, cleanText: text };
    }
    const match = text.match(/<<<ITINERARY_CARD>>>([\s\S]*?)<<<END_ITINERARY_CARD>>>/);
    if (!match) return { cardData: null, cleanText: text };
    try {
      const cardData = JSON.parse(match[1].trim()) as ItineraryCardData;
      const cleanText = text.replace(/<<<ITINERARY_CARD>>>[\s\S]*?<<<END_ITINERARY_CARD>>>/, '').trim();
      return { cardData, cleanText };
    } catch {
      return { cardData: null, cleanText: text };
    }
  }

  // Initial welcome message
  useEffect(() => {
    if (messages.length === 0) {
      setTimeout(() => {
        const welcome: Message = {
          id: 'welcome',
          text: "Hi Friend, I'm GeTS bot!\nTraveling soon? I can help you dig thru some ideas.",
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
    setIsLoading(true);
    setError(null);

    // Define botMsgId FIRST so we can exclude it from history
    const botMsgId = (Date.now() + 1).toString();

    // Build clean conversation history — exclude:
    // 1. The welcome message (not a real exchange)
    // 2. The current bot message being streamed (not complete yet)
    // 3. Any empty messages (incomplete streams)
    const conversationHistory = messages
      .filter(m =>
        m.id !== 'welcome' &&
        m.id !== botMsgId &&
        m.text.trim().length > 0
      )
      .map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-9e89e.up.railway.app';
      console.log(`[GeTS AI] Connecting to backend at: ${apiBaseUrl}`);

      const response = await fetch(`${apiBaseUrl}/chat/stream`, {
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
    <>
      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-[80px] sm:bottom-[88px] right-4 sm:right-6 w-[calc(100vw-2rem)] sm:w-[360px] h-[calc(100dvh-120px)] sm:h-[560px] max-h-[700px] bg-white shadow-2xl flex flex-col z-[100] border border-slate-200 rounded-lg overflow-hidden"
          >
            {/* Header */}
            <div className="bg-[#CC0000] px-4 py-3 flex items-center justify-between flex-shrink-0">
              <h3 className="font-semibold text-[14px] text-white tracking-wide">GeTS AI Assistant</h3>
              <button
                onClick={toggleChat}
                className="hover:bg-white/20 p-1 rounded transition-colors text-white"
                aria-label="Close Chat"
              >
                <X size={18} />
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-[#f7f7f7] chat-scrollbar">
              {messages.map((msg) => {
                if (msg.sender === 'bot') {
                  const { cardData, cleanText } = parseItineraryCard(msg.text);
                  return (
                    <div key={msg.id} className="flex items-start gap-2.5">
                      <BotAvatar />
                      <div className="flex flex-col items-start" style={{ maxWidth: 'calc(100% - 44px)' }}>
                        {cardData && <ItineraryCard data={cardData} />}
                        {cleanText.length > 0 && (
                          <div
                            className="bg-white px-3 py-2.5 text-[13px] leading-relaxed text-slate-800 shadow-sm border border-slate-100"
                            style={{ borderRadius: '0 8px 8px 8px', marginTop: cardData ? 6 : 0 }}
                          >
                            {cleanText.split('\n').map((line, i, arr) => (
                              <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
                            ))}
                          </div>
                        )}
                        <span className="text-[10px] text-slate-400 mt-1 ml-0.5">
                          {formatTimestamp(msg.timestamp)}
                        </span>
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="flex flex-col items-end" style={{ maxWidth: '80%' }}>
                      <div
                        className="bg-[#CC0000] text-white px-3 py-2.5 text-[13px] leading-relaxed shadow-sm"
                        style={{ borderRadius: '8px 0 8px 8px' }}
                      >
                        {msg.text}
                      </div>
                      <span className="text-[10px] text-slate-400 mt-1">
                        {formatTimestamp(msg.timestamp)}
                      </span>
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="flex items-start gap-2.5">
                  <BotAvatar />
                  <div
                    className="bg-white border border-slate-100 px-4 py-3 shadow-sm flex gap-1.5 items-center"
                    style={{ borderRadius: '0 8px 8px 8px' }}
                  >
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0s' }} />
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.2s' }} />
                    <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.4s' }} />
                  </div>
                </div>
              )}

              {error && (
                <div className="flex justify-center">
                  <div className="bg-red-50 text-red-600 px-4 py-2 rounded text-[11px] flex items-center gap-2 border border-red-100">
                    <AlertCircle size={13} />
                    {error}
                  </div>
                </div>
              )}

              {/* Quick Replies — vertical stack, shown after welcome message only */}
              {messages.length === 1 && !isLoading && (
                <div className="flex flex-col gap-2 mt-1 ml-10">
                  <p className="text-[11px] text-slate-500 italic mb-0.5">
                    What type of trip are you planning?
                  </p>
                  {QUICK_REPLIES.map((reply) => (
                    <button
                      key={reply}
                      onClick={() => handleSend(reply)}
                      className="w-full py-2.5 px-4 border border-[#CC0000] text-[#CC0000] text-[13px] hover:bg-[#CC0000] hover:text-white transition-all bg-white text-left"
                      style={{ borderRadius: 4 }}
                    >
                      {reply}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* CTA Strip — shown after bot has sent its second response */}
            {messages.filter(m => m.sender === 'bot').length >= 2 && (
              <div className="px-3 pt-2.5 pb-2 bg-white border-t border-slate-100 flex-shrink-0">
                <p className="text-[9.5px] text-slate-400 font-medium uppercase tracking-widest text-center mb-2">
                  Talk to our travel experts
                </p>
                <div className="flex gap-2">
                  <a
                    href="tel:+919910903434"
                    className="flex-1 flex flex-col items-center justify-center gap-1 py-2.5 rounded border border-[#CC0000] hover:bg-[#CC0000] transition-all group"
                  >
                    <Phone size={13} className="text-[#CC0000] group-hover:text-white transition-colors" />
                    <span className="text-[10px] font-semibold text-[#CC0000] group-hover:text-white transition-colors">Mobile</span>
                  </a>
                  <a
                    href="tel:+911246585800"
                    className="flex-1 flex flex-col items-center justify-center gap-1 py-2.5 rounded border border-[#CC0000] hover:bg-[#CC0000] transition-all group"
                  >
                    <PhoneCall size={13} className="text-[#CC0000] group-hover:text-white transition-colors" />
                    <span className="text-[10px] font-semibold text-[#CC0000] group-hover:text-white transition-colors">Landline</span>
                  </a>
                  <a
                    href="mailto:info@getsholidays.com"
                    className="flex-1 flex flex-col items-center justify-center gap-1 py-2.5 rounded border border-slate-200 hover:border-[#CC0000] hover:bg-[#CC0000] transition-all group"
                  >
                    <Mail size={13} className="text-slate-400 group-hover:text-white transition-colors" />
                    <span className="text-[10px] font-semibold text-slate-400 group-hover:text-white transition-colors">Email</span>
                  </a>
                </div>
              </div>
            )}

            {/* Input Area */}
            <div className="px-4 pt-3 pb-2 bg-white border-t border-slate-200 flex-shrink-0">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
                  placeholder="Type a message..."
                  className="flex-1 text-[13px] text-slate-700 placeholder:text-slate-400 outline-none border-none bg-transparent"
                />
                <button
                  onClick={() => handleSend(input)}
                  disabled={!input.trim() || isLoading}
                  className="text-slate-400 hover:text-[#CC0000] transition-colors disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0"
                >
                  <Send size={17} />
                </button>
              </div>
              <div className="mt-2 pt-2 border-t border-slate-100">
                <p className="text-center text-[9px] text-slate-400 font-medium uppercase tracking-widest">
                  ⚡ Powered by GeTS AI
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Bubble */}
      <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-[110]">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={toggleChat}
          className="relative w-12 h-12 sm:w-14 sm:h-14 bg-[#CC0000] rounded-full flex items-center justify-center text-white shadow-2xl hover:shadow-red-900/20 transition-all border-2 border-white/20"
        >
          {isOpen ? <X size={24} /> : <MessageCircle size={24} fill="white" />}

          {notificationCount > 0 && !isOpen && (
            <span className="absolute -top-1 -right-1 w-5 h-5 sm:w-6 sm:h-6 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-white animate-bounce">
              {notificationCount}
            </span>
          )}
        </motion.button>
      </div>
    </>
  );
}
