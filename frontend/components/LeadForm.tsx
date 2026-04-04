'use client';

import React, { useState } from 'react';
import { Send, CheckCircle } from 'lucide-react';

interface LeadFormProps {
  onSubmit: (name: string, contact: string) => void;
}

export default function LeadForm({ onSubmit }: LeadFormProps) {
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!name.trim() || !contact.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      onSubmit(name.trim(), contact.trim());
      setSubmitted(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: '#edf7f2',
          border: '1px solid #b6dfc9',
          borderRadius: 8,
          padding: '10px 12px',
          marginTop: 6,
          fontSize: 12.5,
          color: '#1a4a3a',
          fontWeight: 500,
        }}
      >
        <CheckCircle size={15} color="#1a4a3a" />
        Details saved — our team will be in touch shortly.
      </div>
    );
  }

  return (
    <div
      style={{
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: '10px 12px',
        marginTop: 6,
        display: 'flex',
        flexDirection: 'column',
        gap: 7,
      }}
    >
      <p style={{ margin: 0, fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        Share your details
      </p>
      <input
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Your name"
        style={{
          fontSize: 14,
          padding: '9px 12px',
          border: '1px solid #e2e8f0',
          borderRadius: 6,
          outline: 'none',
          color: '#1e293b',
          background: '#fff',
        }}
      />
      <input
        type="text"
        value={contact}
        onChange={e => setContact(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleSubmit()}
        placeholder="WhatsApp / Phone / Email"
        style={{
          fontSize: 14,
          padding: '9px 12px',
          border: '1px solid #e2e8f0',
          borderRadius: 6,
          outline: 'none',
          color: '#1e293b',
          background: '#fff',
        }}
      />
      {error && (
        <p style={{ margin: 0, fontSize: 11, color: '#dc2626' }}>{error}</p>
      )}
      <button
        onClick={handleSubmit}
        disabled={!name.trim() || !contact.trim() || submitting}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6,
          background: !name.trim() || !contact.trim() || submitting ? '#94a3b8' : '#1a4a3a',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '10px 14px',
          fontSize: 14,
          fontWeight: 600,
          cursor: !name.trim() || !contact.trim() || submitting ? 'not-allowed' : 'pointer',
          transition: 'background 0.15s',
        }}
      >
        <Send size={12} />
        {submitting ? 'Sending…' : 'Send to GeTS team'}
      </button>
    </div>
  );
}
