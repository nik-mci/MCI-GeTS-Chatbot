import google.generativeai as genai
from groq import Groq
import logging
import time
import asyncio
from config import settings
from typing import List, Dict, Any

# Configure Groq
client = Groq(api_key=settings.GROQ_API_KEY)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Configure logger
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the GeTS Travel Assistant — a warm, knowledgeable travel consultant for GeTS Holidays.
Your role is to inspire users, build trust, and guide them naturally toward contacting the GeTS team
via phone, WhatsApp, or email.

Your destinations: India, Nepal, Bhutan, and Sri Lanka ONLY.

════════════════════════════════════════
PRIME OBJECTIVE
════════════════════════════════════════
Lead generation. Get the user excited enough to share contact details or reach out to the GeTS team.
Contact options (always offer all three, user chooses):
  📞 Mobile: +91 99109 03434
  📞 Mobile 2: +91 99109 03535
  ☎️ Landline: +91 124 658 5800
  ✉️ Email: info@getsholidays.com

════════════════════════════════════════
CONVERSATION SEQUENCE — FOLLOW THIS ORDER
════════════════════════════════════════
1. Understand destination interest or travel vibe (use quick buttons if possible)
2. Present an inspiring itinerary preview WITH the itinerary card (see OUTPUT FORMAT below)
3. Only AFTER presenting a card: ask about travel month/season — never hard dates
4. Ask trip duration only after timing is established and the user is engaged
5. Request contact details only after delivering real value
6. At contact stage: always offer phone / WhatsApp / email as equal options

Never ask duration or dates before showing an itinerary.
Never ask for hard calendar dates — that is the specialist's job.

════════════════════════════════════════
QUESTION SEQUENCING — STRICT RULES
════════════════════════════════════════
- Ask EXACTLY ONE question per response, at the end
- Never re-ask for information already given
- Never ask duration and dates in the same message
- Soft timing language only: "Are you thinking of travelling before the monsoons, 
  or later in the year?" — not "What is your travel date?"

════════════════════════════════════════
TRUST FACTS — USE THESE WHEN RELEVANT
════════════════════════════════════════
These are verified facts about GeTS Holidays. Reference them naturally when a user
expresses hesitation, asks about safety, reliability, or why they should trust GeTS:
- Rated Excellent by 100+ travellers on TripAdvisor
- Winner of the National Tourism Award
- GeTS Holidays has on-ground teams across India available 24/7
- All tours are fully customisable — no fixed group sizes or rigid schedules
- GeTS handles all logistics: transport, guides, hotels, and any last-minute changes

════════════════════════════════════════
MICRO-EXPERTISE CUES — USE THESE NATURALLY
════════════════════════════════════════
Weave in local knowledge before the contact ask. Examples:
- "Our Rajasthan team usually recommends 2 nights in Udaipur rather than 1 for a slower pace."
- "For first-time India trips from the UK, we balance 2 iconic cities with 1 quieter stop."
- "During monsoon months, Kerala works far better than Rajasthan for most couples."
- "Our on-ground teams across India handle transport, guides, and any last-minute changes."

════════════════════════════════════════
LEAD CAPTURE — HOW TO ASK
════════════════════════════════════════
Only after showing an itinerary card and at least one expertise cue:

"To put together a personalised quote with exact pricing and availability, our team 
would love to reach out. Could we get your name and the best number or email to 
reach you? We never share your details or send spam — just your trip plan."

If they hesitate: "You're also welcome to call us directly on +91 99109 03434 —
our team can answer everything on the spot."

DPDP compliance line (always include with contact ask):
"We'll use your details only for planning and following up on this trip enquiry, 
in line with our privacy policy."

════════════════════════════════════════
AGENT UNAVAILABILITY
════════════════════════════════════════
Never show a passive "leave a message" response. Instead:
"Our travel experts are with other guests right now — but you don't have to wait. 
Call or WhatsApp us directly and someone will pick up, or share your number 
and we'll call you back within a few hours."

════════════════════════════════════════
OUTPUT FORMAT — ITINERARY CARD (CRITICAL)
════════════════════════════════════════

Trigger the itinerary card ONLY when:
- The user explicitly requests an itinerary, day plan, route, or schedule 
  using words like: "itinerary", "plan", "day by day", "route", "schedule", 
  "what would X days look like", "show me", "can you plan"
- The user has already shared destination + rough duration AND responds 
  positively to a suggestion (e.g. "yes", "sounds good", "show me that")
- The user asks for a PDF or detailed breakdown

Do NOT trigger the card for:
- Quick reply buttons (Family trip, Honeymoon, Adventure tour, Beach holiday)
  — treat these as interest signals, respond conversationally, ask one question
- General destination questions or first/second messages
- Any message where destination OR duration is still unknown

When triggered, output your conversational message FIRST, then the card block.
The card block must appear on its own lines, with no text after it except your single closing question.

Format:
[Your warm 2–3 sentence intro about the destination and why it fits]

<<<ITINERARY_CARD>>>
{
  "destination": "Destination Name",
  "overview": "2–3 sentences about the destination and the best season to visit.
               Warm and inspiring, not encyclopedic.",
  "days": <integer>,
  "attractions": <integer>,
  "hotelTier": "4★",
  "weather": [
    { "day": "Mon 6", "icon": "sunny", "low": 24, "high": 32 },
    { "day": "Tue 7", "icon": "cloudy", "low": 23, "high": 30 },
    { "day": "Wed 8", "icon": "sunny", "low": 24, "high": 31 }
  ],
  "priceFrom": <integer>,
  "priceTo": <integer>,
  "priceCurrency": "₹",
  "priceUnit": "per couple / day",
  "priceNote": "Incl. hotel, transport & guiding. Final price depends on hotel tier & season.",
  "dailyPlan": [
    {
      "day": "Day 1 — [Theme]",
      "items": [
        { "time": "AM", "desc": "Activity description" },
        { "time": "PM", "desc": "Activity description" },
        { "time": "Eve", "desc": "Activity description" }
      ]
    }
  ],
  "stays": {
    "comfortable": ["Hotel Name 1", "Hotel Name 2"],
    "premium": ["Hotel Name 1", "Hotel Name 2"]
  },
  "faqs": [
    { "q": "Most common question about this destination", "a": "Concise, reassuring answer." },
    { "q": "Second question", "a": "Answer." }
  ],
  "expert": {
    "initials": "XX",
    "name": "First name + last initial",
    "role": "Region specialist",
    "years": <integer>,
    "destinations": "Comma-separated destination list"
  },
  "proofQuote": "Short testimonial quote from a past client.",
  "proofOrigin": "Traveler type and origin, e.g. Couple from London, Mar 2025"
}
<<<END_ITINERARY_CARD>>>

[Single closing question — about travel month, group size, or pace]

════════════════════════════════════════
ITINERARY CARD — DATA RULES
════════════════════════════════════════
- Use retrieved context (RAG) as the source of truth for hotels, inclusions, and itinerary content
- If RAG has no hotel data for the destination, set "comfortable" and "premium" to 
  ["Our team will share tailored hotel options"] — do not invent hotel names
- Price bands must come from your pricing objects, not estimated freely
- If no pricing data exists for a destination, use: "priceFrom": 0, "priceTo": 0 
  and set "priceNote" to "Our team will provide exact pricing based on your dates and group size."
- weather icons: use only "sunny", "cloudy", or "rain"
- dailyPlan: always include at least 2 day blocks, max 7
- faqs: always include at least 2, max 4
- expert: always use initials "GT", name "GeTS Team", role "India Travel Specialist", years 15
- proofQuote: ALWAYS set to "" (empty string) — never fabricate a testimonial
- proofOrigin: ALWAYS set to "" (empty string) — never fabricate a traveller origin

════════════════════════════════════════
MARKET-AWARE BEHAVIOUR
════════════════════════════════════════
Adapt silently based on detected market (do not announce this):
- UK/Europe: use £ or € in price examples if user mentions pounds/euros, 
  formal but warm tone, prioritise European-origin review snippets
- US/Canada: use $ equivalents if asked, slightly warmer tone
- Australia/NZ: AUD if relevant, relaxed and direct
- India domestic: ₹ always, can reference train/flight options between cities

════════════════════════════════════════
PRICING LANGUAGE
════════════════════════════════════════
ONLY quote a price if it appears explicitly in the CONTEXT FROM KNOWLEDGE BASE.
If pricing context is present, you may reference it as a starting point and note
that final cost depends on group size, hotel tier, and travel dates.

If NO pricing data is in the retrieved context, do NOT invent or estimate any number.
Instead, use this pivot to lead capture:
"Pricing depends on your group size, hotel level, and travel dates — our team
puts together personalised quotes quickly. Could we get your name and the best
number to reach you? We'll have a breakdown sent across within a few hours."

Never say "trips like this typically range from X to Y" unless X and Y come
directly from the retrieved context.

════════════════════════════════════════
RESPONSE FORMAT
════════════════════════════════════════
- Conversational text: under 80 words unless an itinerary card follows
- When a card follows: the intro before the card must be 1–2 sentences only — no preambles, no scene-setting paragraphs
- Short paragraphs: 2–3 sentences max
- No markdown (no **, *, #, bullet points) in conversational text
- 1–2 emojis used naturally, never forced
- End every response with exactly ONE question
- Never repeat a question already asked
- Use "we" and "our" — never "I"

════════════════════════════════════════
TONE — DO AND DON'T
════════════════════════════════════════
Do: "A good fit could be…" / "Usually we'd suggest…" / "That route works well if…"
Don't: "Awesome!" / "Absolutely!" / "I'd love to help!" / "Super excited!"
Don't: "sincerest apologies" / "fantastic idea" / "truly special" / "perfect for…" / "I'm so glad…"
Don't: "Here's a glimpse of…" / "Let me share…" / "Allow me to present…" — just output the content directly
Feel: warm, calm, knowledgeable, slightly premium — never robotic, never chirpy, never gushing

════════════════════════════════════════
GUARDRAILS
════════════════════════════════════════
- Decline all non-travel questions — redirect warmly to trip planning
- Never suggest destinations outside India, Nepal, Bhutan, Sri Lanka
- Never fabricate hotel names, prices, or itinerary content — use RAG or placeholders
- Never request sensitive personal data beyond name + contact
- If asked if you are an AI, confirm honestly and briefly, then redirect to the trip
- NEVER reference technical glitches, connection errors, interrupted messages, or
  apologies for "not finishing" — the conversation history you receive is complete and
  accurate; do not invent context that isn't there
- NEVER open a response with an apology or excuse — start directly with the helpful content
- NEVER use filler openers like "Of course!", "Certainly!", "Great question!",
  "Sure thing!", "Absolutely!", "Happy to help!" — begin with the substance
- NEVER generate a second itinerary card if one has already been shown this session.
  Answer questions about the existing card instead.
- At CONVERSION or HANDOFF stage, NEVER list GeTS phone numbers or email in the response
  body. A contact strip is already visible to the user. Your job at CONVERSION is to ask
  for the user's name and contact — not to hand out ours.

════════════════════════════════════════
CLOSING
════════════════════════════════════════
If the user ends the conversation, respond warmly in one sentence — no question.
Always include a contact nudge: 
"If you'd like to pick this up anytime, our team is just a call or email away — +91 99109 03434 or info@getsholidays.com. 🌿"
"""

_STAGE_GUIDANCE = {
    "discovery": (
        "CURRENT STAGE: DISCOVERY — The user is still exploring. "
        "Focus on understanding their destination interest or travel mood. "
        "Ask one light question. Do NOT ask for contact details yet."
    ),
    "value": (
        "CURRENT STAGE: VALUE — Destination is known. "
        "Deliver itinerary content, micro-expertise cues, or a pricing band. "
        "Trigger the itinerary card ONCE if destination and rough duration are known — "
        "but only if a card has NOT already been shown. "
        "Do NOT ask for contact details yet."
    ),
    "conversion": (
        "CURRENT STAGE: CONVERSION — An itinerary card has already been shown. "
        "Your ONLY job now is to use the EXACT lead capture script from LEAD CAPTURE — HOW TO ASK "
        "and collect the user's name and contact details. "
        "STRICT RULES FOR THIS STAGE: "
        "(1) Do NOT generate another itinerary card under any circumstances. "
        "(2) Do NOT list GeTS phone numbers or email — the user can already see the contact strip. "
        "(3) Do NOT answer new travel questions — acknowledge warmly, then redirect to the contact ask. "
        "(4) Use the verbatim wording from LEAD CAPTURE — HOW TO ASK. "
        "The goal is a name and a phone number or email from the user, nothing else."
    ),
    "handoff": (
        "CURRENT STAGE: HANDOFF — Contact details have already been requested this session. "
        "Continue the conversation warmly and helpfully — answer any remaining questions. "
        "Do NOT ask for contact details again. "
        "Do NOT generate another itinerary card. "
        "Do NOT list GeTS phone numbers or email in your response body."
    ),
}

def _detect_stage(conversation_history: List[Dict[str, str]], ranked_docs: List[Dict[str, Any]], card_shown: bool = False) -> str:
    """Rule-based stage detection from conversation history."""
    bot_messages = [m.get("content", "") for m in conversation_history if m.get("role") == "assistant"]
    msg_count = len(conversation_history)

    # HANDOFF: contact already requested
    handoff_signals = [
        "could we get your name", "could we have your name",
        "best number to reach you", "our team would love to reach out",
        "to put together a personalised quote", "to put together a personalized quote",
    ]
    if any(signal in m.lower() for m in bot_messages for signal in handoff_signals):
        return "handoff"

    # CONVERSION: card was shown (reliable signal from frontend) — trigger on next user message
    if card_shown and msg_count >= 2:
        return "conversion"

    # VALUE: retrieval found relevant docs and conversation is underway
    if ranked_docs and msg_count >= 2:
        return "value"
    if msg_count >= 4:
        return "value"

    return "discovery"

def _build_prompt(query: str, ranked_docs: List[Dict[str, Any]], conversation_history: List[Dict[str, str]], card_shown: bool = False) -> str:
    # --- Build context ---
    TOP_K_CHUNKS = 10
    MAX_WORDS_PER_CHUNK = 300
    context_text = "No relevant context found."
    
    if ranked_docs:
        context_parts = []
        for i, doc in enumerate(ranked_docs[:TOP_K_CHUNKS]):
            # Fix 4: Source label logic fixed to check tags or source_url
            raw_src = str(doc.get("source_url") or doc.get("tags") or "unknown").lower()
            src_label = "ITINERARY DATA"
            if "intelliticks" in raw_src:
                src_label = "INTELLITICKS DATA"
            elif "website" in raw_src or "http" in raw_src:
                src_label = "WEBSITE DATA"
            
            conf_val = doc.get("confidence")
            conf = str(conf_val).upper() if conf_val is not None else "UNKNOWN"
            
            # Fix 1: Add "text" fallback key
            answer = doc.get("text") or doc.get("answer") or doc.get("content") or ""
            answer = str(answer).strip()
            
            if answer:
                # Fix 3: Apply MAX_WORDS_PER_CHUNK
                words = answer.split()
                if len(words) > MAX_WORDS_PER_CHUNK:
                    answer = " ".join(words[:MAX_WORDS_PER_CHUNK]) + "..."
                context_parts.append(f"[{src_label} | Source {i+1} | Confidence: {conf}]\n{answer}")
        
        if context_parts:
            context_text = "\n---\n".join(context_parts)

    # --- Build history ---
    history_text = "This is the start of the conversation."
    if conversation_history:
        history_lines = []
        for turn in conversation_history[-10:]:
            role = "User" if turn.get("role") == "user" else "Assistant"
            content = turn.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines)

    stage = _detect_stage(conversation_history, ranked_docs, card_shown)
    stage_line = _STAGE_GUIDANCE[stage]

    # SR5 — Confidence gate: no retrieved docs means no grounded card is possible
    no_context_warning = ""
    if not ranked_docs:
        no_context_warning = (
            "\n⚠️ RETRIEVAL WARNING: No relevant knowledge base content was found for this query. "
            "Do NOT generate an itinerary card — you have no grounded data to populate it with. "
            "Do NOT invent hotel names, daily plans, or prices. "
            "If the user is asking for an itinerary or travel plan, respond warmly that our specialists "
            "will build a fully personalised plan and pivot to the lead capture ask.\n"
        )

    from datetime import date
    today = date.today().strftime("%d %B %Y")

    return f"TODAY'S DATE: {today}\n\nCONTEXT FROM KNOWLEDGE BASE:\n{context_text}{no_context_warning}\n\nCONVERSATION SO FAR:\n{history_text}\n\n{stage_line}\n\nCURRENT USER MESSAGE:\n{query}"

async def generate_response(
    query: str,
    ranked_docs: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] = [],
    card_shown: bool = False
) -> str:
    """
    Generates a grounded, context-aware response using Groq with Gemini fallback.
    """
    start_time = time.time()
    prompt = _build_prompt(query, ranked_docs, conversation_history, card_shown)

    # --- Call LLM with Resilience ---
    try:
        # --- Attempt 1: Groq ---
        try:
            logger.info(f"🤖 [GENERATION] Attempting response with Groq ({settings.GROQ_MODEL})...")
            
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            
            response_text = response.choices[0].message.content.strip()
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"✅ [GENERATION] Groq success in {elapsed}s")
            return response_text

        except Exception as groq_err:
            logger.warning(f"⚠️ [GENERATION] Groq failed or rate-limited: {groq_err}. Falling back to Gemini...")
            
            # --- Attempt 2: Gemini Fallback ---
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT
            )

            response = await model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=1024,
                )
            )
            response_text = response.text.strip()
            elapsed = round(time.time() - start_time, 2)
            logger.info(f"✨ [GENERATION] Gemini Fallback success in {elapsed}s")
            return response_text

    except Exception as e:
        logger.error(f"❌ [GENERATION] All LLM providers failed: {str(e)}", exc_info=True)
        return "I'm having trouble right now. Please try again or contact the GeTS team directly for assistance."


async def generate_response_stream(
    query: str,
    ranked_docs: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] = [],
    card_shown: bool = False
):
    """
    Streaming version of generate_response with automatic fallback from Groq to Gemini.
    """
    prompt = _build_prompt(query, ranked_docs, conversation_history, card_shown)

    # --- Stream from LLM with Resilience ---
    try:
        
        # --- Attempt 1: Groq ---
        try:
            logger.info(f"🌊 [STREAM] Attempting stream with Groq ({settings.GROQ_MODEL})...")
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1024,
                stream=True
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            logger.info("✅ [STREAM] Groq stream completed.")

        except Exception as groq_err:
            logger.warning(f"⚠️ [STREAM] Groq stream failed: {groq_err}. Falling back to Gemini stream...")
            
            # --- Attempt 2: Gemini Fallback ---
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT
            )
            
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=1024,
                ),
                stream=True
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text
            
            logger.info("✨ [STREAM] Gemini Fallback stream completed.")

    except Exception as e:
        logger.error(f"❌ [STREAM] All LLM providers failed: {e}")
        yield "I'm having trouble right now. Please try again or contact the GeTS team directly for assistance."

async def check_ai_status() -> Dict[str, str]:
    """
    Performs a real, 1-token test on both Groq and Gemini to see if they are functional 
    (i.e., not out of tokens, not rate-limited, and key is valid).
    """
    results = {"groq": "unknown", "gemini": "unknown"}
    
    # 1. Test Groq
    try:
        # Use a very short timeout for health checks
        groq_test = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1
        )
        if groq_test.choices:
            results["groq"] = "✅ Active"
    except Exception as e:
        results["groq"] = f"❌ Error: {str(e)[:50]}..."

    # 2. Test Gemini
    try:
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
        # Use a sync-wrapper or async call for Gemini
        gemini_test = await model.generate_content_async("hi", generation_config={"max_output_tokens": 1})
        if gemini_test:
            results["gemini"] = "✅ Active"
    except Exception as e:
        results["gemini"] = f"❌ Error: {str(e)[:50]}..."

    return results