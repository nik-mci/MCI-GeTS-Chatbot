# GeTS Chatbot — Real Data Required

This file tracks all content and data that needs to be sourced from the GeTS team
before the chatbot can be considered sales-ready (not just demo-ready).

Items are ranked by impact on trust and conversion.

---

## 1. CLIENT TESTIMONIALS / PROOF QUOTES (CRITICAL)
**Impact:** Highest — fabricated quotes are currently shown on every itinerary card
**Used in:** ItineraryCard.tsx `proofQuote` and `proofOrigin` fields

Collect 30–50 real client testimonials. For each one, we need:
- [ ] The quote itself (1–2 sentences, specific and vivid — not "great trip!")
- [ ] Traveller type (e.g. "Couple", "Family of 4", "Solo traveller")
- [ ] Origin country/city (e.g. "London, UK", "Sydney, Australia")
- [ ] Month and year of travel (e.g. "Oct 2024")
- [ ] Destination they travelled to (e.g. "Kerala", "Rajasthan")
- [ ] Trip type/theme if known (e.g. "Honeymoon", "Wildlife Safari")

**Sources to pull from:**
- Google Reviews (getsholidays.com listing)
- TripAdvisor reviews
- Email feedback/thank-you messages from past clients
- WhatsApp messages from clients (with permission)

**Format needed:** Any format is fine — raw text, spreadsheet, copy-paste from reviews.
We will structure and ingest them.

---

## 2. PACKAGE PRICING DATA (HIGH)
**Impact:** High — bot currently cannot quote any prices for 56 out of 60 destinations
**Used in:** ItineraryCard.tsx price band, generation.py pricing language

Only 4 itineraries currently have real prices (all from 2021, USD-denominated):
- North India with Mumbai — USD 788/person (9N/10D, twin sharing)
- Wildlife Safari — USD 2,838/person (9N/10D, twin sharing)
- Luxury Golden Triangle — USD 388/person (5N/6D, group of 4)
- Kashmir + Leh & Ladakh — USD 2,098/package (14N/15D)

For each destination/package, we need:
- [ ] Destination(s) covered
- [ ] Duration (nights/days)
- [ ] Price from / price to (band, not exact)
- [ ] Currency (INR or USD)
- [ ] Per person or per couple
- [ ] Hotel tier this applies to (budget / standard / luxury)
- [ ] Season validity (e.g. "Oct–Mar", "year-round")
- [ ] What's included (hotel, transport, guide, meals?)

**Priority destinations (highest user demand based on current queries):**
- [ ] Kerala
- [ ] Rajasthan
- [ ] Goa
- [ ] Bhutan
- [ ] Andaman
- [ ] Golden Triangle (Delhi–Agra–Jaipur)
- [ ] Himachal Pradesh
- [ ] Kashmir

---

## 3. EXPERT / TEAM PROFILES (MEDIUM)
**Impact:** Medium — expert strip on itinerary card currently shows "GeTS Team / 15 yrs" for all destinations
**Used in:** ItineraryCard.tsx expert strip

For each regional specialist on the GeTS team, we need:
- [ ] First name + last initial (e.g. "Priya S.")
- [ ] Role/title (e.g. "South India Specialist")
- [ ] Years of experience
- [ ] Destinations they specialise in (comma-separated)
- [ ] Optional: photo or initials for avatar

**Minimum viable:** 3–5 team members covering the main regions (South India, North India, Northeast, International — Bhutan/Nepal/Sri Lanka)

---

## 4. WHATSAPP BUSINESS NUMBER (LOW — QUICK WIN)
**Impact:** Low but immediate — placeholder currently uses the mobile number
**Used in:** ChatWidget.tsx `WHATSAPP_NUMBER` constant

- [ ] Confirm the correct WhatsApp Business number for GeTS
- [ ] Current placeholder: `919910903434` (same as mobile)
- [ ] If different, update `WHATSAPP_NUMBER` in ChatWidget.tsx (one-line change)

---

## 5. OBJECTION HANDLING CONTENT (MEDIUM)
**Impact:** Medium — bot falls back to LLM general knowledge for common objections
**Used in:** Vector DB (new content type needed)

Common objections for India travel that need GeTS-specific answers:
- [ ] "Is India safe for solo/female travellers?"
- [ ] "Is it too hot / what's the best time to visit?"
- [ ] "We've never done a guided tour — is it flexible?"
- [ ] "What if something goes wrong on the trip?"
- [ ] "How does GeTS handle flight cancellations or delays?"
- [ ] "Do you handle visa applications?"
- [ ] "What's the difference between your budget and luxury packages?"

**Format needed:** Q&A pairs — a natural question and a 2–4 sentence GeTS-specific answer.

---

## 6. 900MB ITINERARY FOLDER (MEDIUM)
**Impact:** Medium — may contain additional destinations and real pricing
**Status:** Folder not yet available for scanning

When the folder is available:
- [ ] Share the folder path
- [ ] We will scan for real pricing data first (extract to pricing.json)
- [ ] Run boilerplate filter before ingesting
- [ ] Ingest clean chunks only
- [ ] Verify vector count stays within Supabase free tier limits (~500MB)

---

## SUMMARY CHECKLIST

| # | Data | Status | Priority |
|---|---|---|---|
| 1 | Client testimonials (30–50) | Not started | Critical |
| 2 | Package pricing bands | Not started | High |
| 3 | Team/expert profiles (3–5) | Not started | Medium |
| 4 | WhatsApp number confirmation | Not started | Low |
| 5 | Objection handling Q&A | Not started | Medium |
| 6 | 900MB itinerary folder | Pending access | Medium |
