'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Send, Globe, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ItineraryCard, { ItineraryCardData } from './ItineraryCard';

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
      {/* Popout Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20, transformOrigin: 'bottom right' }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="fixed bottom-[90px] sm:bottom-[100px] inset-x-4 sm:inset-x-auto sm:right-6 w-auto sm:w-[350px] h-[calc(100dvh-150px)] sm:h-[520px] max-h-[650px] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col border border-slate-200 z-[100]"
          >
            {/* Header - Using Hardcoded Hex for Brand Consistency */}
            <div className="bg-[#CC0000] p-3 sm:p-4 flex items-center justify-between text-white shadow-md relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                  <Globe size={18} />
                </div>
                <div>
                  <h3 className="font-bold text-sm leading-tight text-white">GeTS AI Assistant</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                    <span className="text-[10px] text-white/90 font-medium">Online</span>
                  </div>
                </div>
              </div>
              <button
                onClick={toggleChat}
                className="hover:bg-white/10 p-1.5 rounded-full transition-colors text-white"
                aria-label="Close Chat"
              >
                <X size={20} />
              </button>
            </div>

            {/* Messages Area - Ensuring clean scrollbar */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scrollbar bg-[#f8fafc]">
              {messages.map((msg) => {
                if (msg.sender === 'bot') {
                  const { cardData, cleanText } = parseItineraryCard(msg.text);
                  return (
                    <div key={msg.id} className="flex justify-start">
                      <div className="max-w-[80%] flex flex-col items-start" style={{ maxWidth: '90%' }}>
                        {cardData && <ItineraryCard data={cardData} />}
                        {cleanText.length > 0 && (
                          <div className="px-4 py-2 rounded-2xl text-[13.5px] leading-relaxed shadow-sm bg-white text-slate-800 border border-slate-100 rounded-tl-none" style={{ marginTop: cardData ? 6 : 0 }}>
                            {cleanText}
                          </div>
                        )}
                        <span className="text-[9px] text-slate-400 mt-1 uppercase font-medium tracking-wider">
                          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                }
                return (
                  <div
                    key={msg.id}
                    className="flex justify-end"
                  >
                    <div className="max-w-[80%] flex flex-col items-end">
                      <div className="px-4 py-2 rounded-2xl text-[13.5px] leading-relaxed shadow-sm bg-[#CC0000] text-white rounded-tr-none">
                        {msg.text}
                      </div>
                      <span className="text-[9px] text-slate-400 mt-1 uppercase font-medium tracking-wider">
                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                );
              })}

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
                  <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-[11px] flex items-center gap-2 border border-red-100">
                    <AlertCircle size={13} />
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
                      className="px-2.5 py-1.5 rounded-full border border-[#CC0000] text-[#CC0000] text-[12px] font-medium hover:bg-[#CC0000] hover:text-white transition-all active:scale-95 bg-white shadow-sm"
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
              <div className="flex gap-2 px-3 py-2 bg-white border-t border-slate-100">
                <a
                  href="tel:+919910903434"
                  className="flex-1 flex items-center justify-center gap-1 rounded-lg text-[11px] font-semibold text-white py-2 px-1"
                  style={{ background: '#1a4a3a' }}
                >
                  📞 Mobile
                </a>
                <a
                  href="tel:+911246585800"
                  className="flex-1 flex items-center justify-center gap-1 rounded-lg text-[11px] font-semibold text-white py-2 px-1"
                  style={{ background: '#1a4a3a' }}
                >
                  ☎️ Landline
                </a>
                <a
                  href="mailto:info@getsholidays.com"
                  className="flex-1 flex items-center justify-center gap-1 rounded-lg text-[11px] font-semibold text-slate-700 py-2 px-1 border border-slate-200 bg-white"
                >
                  ✉️ Email
                </a>
              </div>
            )}

            {/* Input Area */}
            <div className="p-3 sm:p-4 bg-white border-t border-slate-100">
              <div className="relative flex items-center gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend(input)}
                  placeholder="Ask about travel..."
                  className="flex-1 bg-slate-50 border-none rounded-xl px-4 py-2.5 text-[13px] focus:ring-2 focus:ring-red-100 outline-none text-slate-700 placeholder:text-slate-400 transition-all"
                />
                <button
                  onClick={() => handleSend(input)}
                  disabled={!input.trim() || isLoading}
                  className="bg-[#CC0000] text-white p-2.5 rounded-xl hover:bg-[#B30000] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
                >
                  <Send size={16} />
                </button>
              </div>
              <p className="text-center text-[9px] text-slate-400 mt-2 font-medium uppercase tracking-widest">
                Powered by GeTS AI
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating Bubble - Fixed Independently */}
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