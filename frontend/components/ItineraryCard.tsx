'use client';

import React, { useState } from 'react';

// ── Types ────────────────────────────────────────────────────────────────────

interface WeatherDay {
  day: string;
  icon: 'sunny' | 'cloudy' | 'rain' | string;
  low: number;
  high: number;
}

interface DayItem {
  time: string;
  desc: string;
}

interface DayPlan {
  day: string;
  items: DayItem[];
}

interface Stays {
  comfortable: string[];
  premium: string[];
}

interface FAQ {
  q: string;
  a: string;
}

interface Expert {
  initials: string;
  name: string;
  role: string;
  years: number;
  destinations: string;
}

export interface ItineraryCardData {
  destination: string;
  dateFrom: string;
  dateTo: string;
  overview: string;
  days: number;
  attractions: number;
  hotelTier: string;
  weather: WeatherDay[];
  priceFrom: number;
  priceTo: number;
  priceCurrency: string;
  priceUnit: string;
  priceNote: string;
  dailyPlan: DayPlan[];
  stays: Stays;
  faqs: FAQ[];
  expert: Expert;
  proofQuote: string;
  proofOrigin: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function weatherIcon(icon: string): string {
  if (icon === 'sunny') return '☀️';
  if (icon === 'cloudy') return '⛅';
  if (icon === 'rain') return '🌧️';
  return '🌤️';
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

// ── Tab definitions ───────────────────────────────────────────────────────────

type Tab = 'overview' | 'daily' | 'stays' | 'faqs';
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'daily', label: 'Daily plan' },
  { id: 'stays', label: 'Stays' },
  { id: 'faqs', label: 'FAQs' },
];

// ── Main component ────────────────────────────────────────────────────────────

export default function ItineraryCard({ data }: { data: ItineraryCardData }) {
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  return (
    <div
      style={{
        borderRadius: 14,
        overflow: 'hidden',
        border: '1px solid #e2e8f0',
        background: '#fff',
        fontSize: 13,
        position: 'relative',
        width: '100%',
        maxWidth: 320,
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          background: '#1a4a3a',
          color: '#fff',
          padding: '12px 14px 10px',
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: 0.2 }}>
          {data.destination}
        </div>
        <div style={{ fontSize: 10.5, opacity: 0.82, marginTop: 2 }}>
          {formatDate(data.dateFrom)} – {formatDate(data.dateTo)}
        </div>
      </div>

      {/* ── Tabs ── */}
      <div
        style={{
          display: 'flex',
          borderBottom: '1px solid #e2e8f0',
          background: '#fff',
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: '7px 2px',
              fontSize: 10.5,
              fontWeight: activeTab === tab.id ? 700 : 500,
              color: activeTab === tab.id ? '#1a4a3a' : '#64748b',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #1a4a3a' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'color 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: '12px 14px', background: '#f8fafc' }}>

        {/* ─── OVERVIEW ─── */}
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Overview paragraph */}
            <p style={{ margin: 0, color: '#334155', lineHeight: 1.55, fontSize: 12.5 }}>
              {data.overview}
            </p>

            {/* Stats row */}
            <div
              style={{
                display: 'flex',
                gap: 6,
                justifyContent: 'space-between',
              }}
            >
              {[
                { label: 'Days', value: data.days },
                { label: 'Attractions', value: data.attractions },
                { label: 'Hotel', value: data.hotelTier },
              ].map((stat) => (
                <div
                  key={stat.label}
                  style={{
                    flex: 1,
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    padding: '6px 4px',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ color: '#1a4a3a', fontWeight: 700, fontSize: 14 }}>
                    {stat.value}
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: 9.5, marginTop: 2 }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>

            {/* Weather */}
            {data.weather && data.weather.length > 0 && (
              <div
                style={{
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '8px 10px',
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
                  Weather forecast
                </div>
                {data.weather.map((w, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '3px 0',
                      borderTop: i > 0 ? '1px solid #f1f5f9' : 'none',
                    }}
                  >
                    <span style={{ fontSize: 11, color: '#475569', width: 52 }}>{w.day}</span>
                    <span style={{ fontSize: 14 }}>{weatherIcon(w.icon)}</span>
                    <span style={{ fontSize: 11, color: '#64748b' }}>
                      {w.low}° – {w.high}°C
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Price band */}
            <div
              style={{
                background: '#edf7f2',
                border: '1px solid #b6dfc9',
                borderRadius: 8,
                padding: '8px 10px',
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 600, color: '#1a4a3a', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>
                Estimated price
              </div>
              <div style={{ fontWeight: 700, fontSize: 15, color: '#1a4a3a' }}>
                {data.priceCurrency}{data.priceFrom.toLocaleString()} – {data.priceCurrency}{data.priceTo.toLocaleString()}
              </div>
              <div style={{ fontSize: 10.5, color: '#2d7a56', marginTop: 2 }}>
                {data.priceUnit}
              </div>
              {data.priceNote && (
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 5, lineHeight: 1.45 }}>
                  {data.priceNote}
                </div>
              )}
            </div>

            {/* Expert strip */}
            {data.expert && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '8px 10px',
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: '50%',
                    background: '#1a4a3a',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: 12,
                    flexShrink: 0,
                  }}
                >
                  {data.expert.initials}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12, color: '#1e293b' }}>
                    {data.expert.name}
                  </div>
                  <div style={{ fontSize: 10.5, color: '#64748b' }}>
                    {data.expert.role} · {data.expert.years} yrs
                  </div>
                  <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 1 }}>
                    {data.expert.destinations}
                  </div>
                </div>
              </div>
            )}

            {/* Proof quote */}
            {data.proofQuote && (
              <div
                style={{
                  borderLeft: '3px solid #1a4a3a',
                  paddingLeft: 10,
                  marginLeft: 2,
                }}
              >
                <p style={{ margin: 0, fontStyle: 'italic', fontSize: 11.5, color: '#475569', lineHeight: 1.5 }}>
                  "{data.proofQuote}"
                </p>
                {data.proofOrigin && (
                  <p style={{ margin: '4px 0 0', fontSize: 10, color: '#94a3b8' }}>
                    — {data.proofOrigin}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─── DAILY PLAN ─── */}
        {activeTab === 'daily' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.dailyPlan && data.dailyPlan.length > 0 ? (
              data.dailyPlan.map((dayBlock, i) => (
                <div
                  key={i}
                  style={{
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      background: '#1a4a3a',
                      color: '#fff',
                      padding: '6px 10px',
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    {dayBlock.day}
                  </div>
                  <div style={{ padding: '6px 10px' }}>
                    {dayBlock.items.map((item, j) => (
                      <div
                        key={j}
                        style={{
                          display: 'flex',
                          gap: 8,
                          padding: '4px 0',
                          borderTop: j > 0 ? '1px solid #f1f5f9' : 'none',
                          alignItems: 'flex-start',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 700,
                            color: '#1a4a3a',
                            textTransform: 'uppercase',
                            letterSpacing: 0.3,
                            width: 26,
                            paddingTop: 1,
                            flexShrink: 0,
                          }}
                        >
                          {item.time}
                        </span>
                        <span style={{ fontSize: 11.5, color: '#334155', lineHeight: 1.45 }}>
                          {item.desc}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <p style={{ margin: 0, color: '#94a3b8', fontSize: 12 }}>
                No daily plan available.
              </p>
            )}
          </div>
        )}

        {/* ─── STAYS ─── */}
        {activeTab === 'stays' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.stays?.comfortable?.length > 0 && (
              <div
                style={{
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '8px 10px',
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
                  Comfortable
                </div>
                {data.stays.comfortable.map((hotel, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 12,
                      color: '#1e293b',
                      padding: '3px 0',
                      borderTop: i > 0 ? '1px solid #f1f5f9' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span style={{ color: '#1a4a3a', fontSize: 14 }}>🏨</span>
                    {hotel}
                  </div>
                ))}
              </div>
            )}

            {data.stays?.premium?.length > 0 && (
              <div
                style={{
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '8px 10px',
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6 }}>
                  Premium
                </div>
                {data.stays.premium.map((hotel, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 12,
                      color: '#1e293b',
                      padding: '3px 0',
                      borderTop: i > 0 ? '1px solid #f1f5f9' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span style={{ fontSize: 14 }}>⭐</span>
                    {hotel}
                  </div>
                ))}
              </div>
            )}

            <div
              style={{
                fontSize: 10.5,
                color: '#64748b',
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '7px 10px',
                lineHeight: 1.5,
              }}
            >
              Our team will confirm availability and pricing for your selected dates before booking.
            </div>
          </div>
        )}

        {/* ─── FAQs ─── */}
        {activeTab === 'faqs' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.faqs && data.faqs.length > 0 ? (
              data.faqs.map((faq, i) => (
                <div
                  key={i}
                  style={{
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    padding: '8px 10px',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 12, color: '#1e293b', marginBottom: 4 }}>
                    {faq.q}
                  </div>
                  <div style={{ fontSize: 11.5, color: '#475569', lineHeight: 1.5 }}>
                    {faq.a}
                  </div>
                </div>
              ))
            ) : (
              <p style={{ margin: 0, color: '#94a3b8', fontSize: 12 }}>
                No FAQs available.
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
