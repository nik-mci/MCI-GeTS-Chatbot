'use client';

import React, { useState, useEffect, useRef } from 'react';
import { MessageCircle, X, Send, Globe, AlertCircle, Phone, Mail, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ItineraryCard, { ItineraryCardData } from './ItineraryCard';
import LeadForm from './LeadForm';

interface Message {
  id: string;
  text: string;
  sender: 'bot' | 'user';
  timestamp: Date;
  showLeadForm?: boolean;
}

const SESSION_MESSAGES_KEY = 'gets_messages';
const SESSION_TIMESTAMP_KEY = 'gets_session_timestamp';
const SESSION_LEAD_KEY = 'gets_lead_captured';
const SESSION_INTENT_KEY = 'gets_intent';
const SESSION_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

interface AccumulatedIntent {
  destinations: string[];
  duration: string | null;
  budget: string | null;
  travel_date: string | null;
  theme: string | null;
}

function mergeIntent(prev: AccumulatedIntent, incoming: Record<string, unknown>): AccumulatedIntent {
  const newDests = Array.isArray(incoming.destination) ? incoming.destination as string[] : [];
  return {
    destinations: Array.from(new Set([...prev.destinations, ...newDests])),
    duration: (incoming.duration as string | null) || prev.duration,
    budget: (incoming.budget as string | null) || prev.budget,
    travel_date: (incoming.travel_date as string | null) || prev.travel_date,
    theme: (incoming.theme as string | null) || prev.theme,
  };
}

function formatHandoffSummary(intent: AccumulatedIntent): string {
  const line = '\u2500'.repeat(28);
  const rows: string[] = ['TRIP INTEREST SUMMARY', line];
  if (intent.destinations.length > 0)
    rows.push(`Destination : ${intent.destinations.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')}`);
  if (intent.duration)   rows.push(`Duration    : ${intent.duration}`);
  if (intent.budget)     rows.push(`Budget      : ${intent.budget}`);
  if (intent.travel_date) rows.push(`Travel date : ${intent.travel_date}`);
  if (intent.theme)      rows.push(`Theme/Type  : ${intent.theme}`);
  if (rows.length === 2) rows.push('No specific trip details captured.');
  rows.push(line);
  return rows.join('\n');
}

function generateSessionId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

const QUICK_REPLIES = [
  "A romantic trip 🏰",
  "For a family trip 👨‍👩‍👧",
  "For a trip with my friends 👥",
  "For a solo trip 🧳",
  "Group Tour 🚢",
];

// TODO: Replace with confirmed GeTS WhatsApp number when available
const WHATSAPP_NUMBER = '919910903434';

function WhatsAppIcon({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
    </svg>
  );
}

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
  const [leadCaptured, setLeadCaptured] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [accumulatedIntent, setAccumulatedIntent] = useState<AccumulatedIntent>({
    destinations: [], duration: null, budget: null, travel_date: null, theme: null,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function parseItineraryCard(text: string): { cardData: ItineraryCardData | null; cleanText: string; cardLoading: boolean } {
    const hasOpen = text.includes('<<<ITINERARY_CARD>>>');
    const hasClose = text.includes('<<<END_ITINERARY_CARD>>>');

    // Card is mid-stream — hide raw JSON, show placeholder
    if (hasOpen && !hasClose) {
      const beforeCard = text.split('<<<ITINERARY_CARD>>>')[0].trim();
      return { cardData: null, cleanText: beforeCard, cardLoading: true };
    }

    // Card fully arrived — parse it
    if (hasOpen && hasClose) {
      const match = text.match(/<<<ITINERARY_CARD>>>([\s\S]*?)<<<END_ITINERARY_CARD>>>/);
      if (!match) return { cardData: null, cleanText: text, cardLoading: false };
      try {
        const cardData = JSON.parse(match[1].trim()) as ItineraryCardData;
        const cleanText = text.replace(/<<<ITINERARY_CARD>>>[\s\S]*?<<<END_ITINERARY_CARD>>>/, '').trim();
        return { cardData, cleanText, cardLoading: false };
      } catch {
        return { cardData: null, cleanText: text, cardLoading: false };
      }
    }

    return { cardData: null, cleanText: text, cardLoading: false };
  }

  // Restore session from localStorage on mount, or start fresh
  useEffect(() => {
    const savedMessages = localStorage.getItem(SESSION_MESSAGES_KEY);
    const savedTimestamp = localStorage.getItem(SESSION_TIMESTAMP_KEY);
    const savedLeadCaptured = localStorage.getItem(SESSION_LEAD_KEY);

    if (savedMessages && savedTimestamp) {
      const age = Date.now() - parseInt(savedTimestamp);
      if (age < SESSION_TTL_MS) {
        const parsed = JSON.parse(savedMessages) as Message[];
        const restored = parsed.map(m => ({
          ...m,
          timestamp: new Date(m.timestamp),
          showLeadForm: false, // never restore ephemeral form state
        }));
        setMessages(restored);
        setLeadCaptured(savedLeadCaptured === 'true');
        setSessionId(generateSessionId());
        const savedIntent = localStorage.getItem(SESSION_INTENT_KEY);
        if (savedIntent) setAccumulatedIntent(JSON.parse(savedIntent));
        return;
      }
    }

    // No valid session — show welcome message
    const newId = generateSessionId();
    setSessionId(newId);
    setTimeout(() => {
      setMessages([{
        id: 'welcome',
        text: "Welcome to GeTS Holidays 🌿\nPlanning a trip to India, Bhutan, Nepal or Sri Lanka? Tell us what you have in mind and we'll help shape it.",
        sender: 'bot',
        timestamp: new Date(),
      }]);
    }, 1000);
  }, []);

  // Persist messages, lead state, and accumulated intent to localStorage after every change
  useEffect(() => {
    if (messages.length === 0) return;
    localStorage.setItem(SESSION_MESSAGES_KEY, JSON.stringify(messages));
    localStorage.setItem(SESSION_TIMESTAMP_KEY, Date.now().toString());
    localStorage.setItem(SESSION_LEAD_KEY, String(leadCaptured));
    localStorage.setItem(SESSION_INTENT_KEY, JSON.stringify(accumulatedIntent));
  }, [messages, leadCaptured, accumulatedIntent]);

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

      const cardShown = messages.some(m => m.sender === 'bot' && m.text.includes('<<<END_ITINERARY_CARD>>>'));

      const response = await fetch(`${apiBaseUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text,
          conversation_history: conversationHistory,
          card_shown: cardShown,
          accumulated_intent: accumulatedIntent,
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
          if (token.startsWith('[INTENT]')) {
            try {
              const intent = JSON.parse(token.slice(8));
              setAccumulatedIntent(prev => mergeIntent(prev, intent));
            } catch { /* malformed intent — skip silently */ }
            continue;
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

      // Detect lead capture trigger in completed response
      const LEAD_TRIGGERS = [
        'could we get your name',
        'could we have your name',
        'may we get your name',
        'may we have your name',
        'would you mind sharing your name',
        'would you like to share your name',
        'to put together a personalised quote',
        'to put together a personalized quote',
        'our team would love to reach out',
        'could we get your contact',
        'share your contact',
        'best number to reach you',
        'best number or email to reach you',
        'name and the best',
        'reach out to you',
      ];
      const lowerFull = fullText.toLowerCase();
      if (!leadCaptured && LEAD_TRIGGERS.some(t => lowerFull.includes(t))) {
        setMessages(prev =>
          prev.map(m => m.id === botMsgId ? { ...m, showLeadForm: true } : m)
        );
      }

    } catch (err) {
      setError("Sorry, I'm having trouble connecting. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const clearSession = () => {
    localStorage.removeItem(SESSION_MESSAGES_KEY);
    localStorage.removeItem(SESSION_TIMESTAMP_KEY);
    localStorage.removeItem(SESSION_LEAD_KEY);
    localStorage.removeItem(SESSION_INTENT_KEY);
    setAccumulatedIntent({ destinations: [], duration: null, budget: null, travel_date: null, theme: null });
    setMessages([]);
    setLeadCaptured(false);
    setError(null);
    setSessionId(generateSessionId());
    setTimeout(() => {
      setMessages([{
        id: 'welcome',
        text: "Welcome to GeTS Holidays 🌿\nPlanning a trip to India, Bhutan, Nepal or Sri Lanka? Tell us what you have in mind and we'll help shape it.",
        sender: 'bot',
        timestamp: new Date(),
      }]);
    }, 400);
  };

  const handleLeadSubmit = async (name: string, contact: string) => {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-9e89e.up.railway.app';
    const recentChat = messages
      .slice(-8)
      .map(m => `${m.sender === 'user' ? 'User' : 'Bot'}: ${m.text.slice(0, 300)}`)
      .join('\n');
    const summary = formatHandoffSummary(accumulatedIntent) + '\n\nRECENT CONVERSATION\n' + recentChat;

    const history = messages
      .filter(m => m.id !== 'welcome' && m.text.trim().length > 0)
      .filter(m => {
        if (m.sender === 'user') return true; // always keep user messages
        const clean = m.text.replace(/<<<ITINERARY_CARD>>>[\s\S]*?<<<END_ITINERARY_CARD>>>/g, '').trim();
        return clean.length > 100; // only keep substantive bot messages
      })
      .map(({ sender, text, timestamp }) => {
        // Replace itinerary card JSON with a short note
        const cardMatch = text.match(/<<<ITINERARY_CARD>>>([\s\S]*?)<<<END_ITINERARY_CARD>>>/);
        let cleanText = text.replace(/<<<ITINERARY_CARD>>>[\s\S]*?<<<END_ITINERARY_CARD>>>/, '').trim();
        if (cardMatch) {
          try {
            const card = JSON.parse(cardMatch[1].trim());
            cleanText = `[Showed itinerary card: ${card.destination}]\n` + cleanText;
          } catch {
            cleanText = '[Showed itinerary card]\n' + cleanText;
          }
        }
        return {
          role: sender === 'user' ? 'user' : 'assistant',
          text: cleanText,
          timestamp: timestamp.toISOString(),
        };
      });

    try {
      await fetch(`${apiBaseUrl}/lead`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, contact, conversation_summary: summary, conversation_history: history }),
      });
    } catch {
      // submission error is shown in LeadForm — don't block the confirmation
    }

    setLeadCaptured(true);
    setMessages(prev => [
      ...prev.map(m => ({ ...m, showLeadForm: false })),
      {
        id: Date.now().toString(),
        text: `Thanks ${name}! Our team will reach out to you at ${contact} shortly. Feel free to keep exploring ideas in the meantime. 🌿`,
        sender: 'bot' as const,
        timestamp: new Date(),
      },
    ]);
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
              <div className="flex items-center gap-1">
                <button
                  onClick={clearSession}
                  className="hover:bg-white/20 p-1 rounded transition-colors text-white/70 hover:text-white"
                  aria-label="Start new conversation"
                  title="Start fresh"
                >
                  <Trash2 size={15} />
                </button>
                <button
                  onClick={toggleChat}
                  className="hover:bg-white/20 p-1 rounded transition-colors text-white"
                  aria-label="Close Chat"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-[#f7f7f7] chat-scrollbar">
              {messages.map((msg) => {
                if (msg.sender === 'bot') {
                  const { cardData, cleanText, cardLoading } = parseItineraryCard(msg.text);
                  return (
                    <div key={msg.id} className="flex items-start gap-2.5">
                      <BotAvatar />
                      <div className="flex flex-col items-start" style={{ maxWidth: 'calc(100% - 44px)' }}>
                        {cleanText.length > 0 && (
                          <div
                            className="bg-white px-3 py-2.5 text-[13px] leading-relaxed text-slate-800 shadow-sm border border-slate-100"
                            style={{ borderRadius: '0 8px 8px 8px', marginBottom: (cardData || cardLoading) ? 6 : 0 }}
                          >
                            {cleanText.split('\n').map((line, i, arr) => (
                              <span key={i}>{line}{i < arr.length - 1 && <br />}</span>
                            ))}
                          </div>
                        )}
                        {cardLoading && (
                          <div
                            className="bg-white border border-slate-100 shadow-sm px-4 py-3 flex gap-1.5 items-center"
                            style={{ borderRadius: 14, width: '100%', maxWidth: 320 }}
                          >
                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0s' }} />
                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.2s' }} />
                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full dot-pulse" style={{ animationDelay: '0.4s' }} />
                            <span className="text-[11px] text-slate-400 ml-1">Building your itinerary…</span>
                          </div>
                        )}
                        {cardData && <ItineraryCard data={cardData} />}
                        {msg.showLeadForm && !leadCaptured && (
                          <LeadForm onSubmit={handleLeadSubmit} />
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
                  <
                    href={`https://wa.me/${WHATSAPP_NUMBER}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex flex-col items-center justify-center gap-1 py-2.5 rounded border border-[#25D366] hover:bg-[#25D366] transition-all group"
                  >
                    <span className="text-[#25D366] group-hover:text-white transition-colors">
                      <WhatsAppIcon size={13} />
                    </span>
                    <span className="text-[10px] font-semibold text-[#25D366] group-hover:text-white transition-colors">WhatsApp</span>
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
