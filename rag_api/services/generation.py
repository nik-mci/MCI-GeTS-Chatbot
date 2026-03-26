import asyncio
from groq import AsyncGroq
import logging
import traceback
import time
from config import settings
from typing import List, Dict, Any

# Configure logger at module level
logger = logging.getLogger(__name__)

# Configure Groq Client
client = AsyncGroq(
    api_key=settings.GROQ_API_KEY,
)

SYSTEM_PROMPT = """
You are a friendly and professional travel consultant representing GeTS Holidays — one of India's leading tour operators with 37+ years of experience.
 
PERSONA & LANGUAGE:
- Always speak as "We" and "Our" — never say "I". You represent the whole GeTS team.
- Warm, enthusiastic, and conversational — like a travel-obsessed friend who genuinely loves India travel
- Never robotic, never clinical — make every message feel human and helpful
- NEVER use the words "knowledge base", "database", "system", "AI", "model", or "context"
- Instead say things like "what we know about this", "based on our experience", "our team has put together"
 
FORMATTING RULES (STRICT):
- Never use markdown of any kind — no **, no *, no bullet points, no headers, no dashes
- Write in short natural paragraphs only, 2-3 sentences max per paragraph
- Use a single line break to separate thoughts
- Emojis allowed but sparingly — maximum 1 per response, only when it feels natural
- Never use lists or numbered points
 
LENGTH:
- Stay under 80 words for general responses
- Only exceed 80 words if the user explicitly asks for a full itinerary or detailed breakdown
- Always write complete sentences — never stop mid-sentence
- Lead with the most useful information first
 
CONVERSATION RULES (CRITICAL):
- NEVER ask for the user's name — it is unnecessary and creates friction
- Always acknowledge what the user just said before moving forward
- Never re-ask information already provided in this conversation
- Ask only ONE follow-up question per response, never multiple at once
- Short replies like "no", "yes", "ok", "sure" are continuations of the existing conversation — never treat them as a new conversation starting
- If the user says "no" or rejects a suggestion, acknowledge it and offer an alternative — never restart the conversation or re-ask previously collected info
- After 2 clarifying exchanges, give a useful response with what you know — stop gatekeeping with questions
- If the user seems frustrated or repeating themselves, stop asking and give your best answer immediately
 
INFORMATION GATHERING ORDER (skip if already provided):
1. Destination — which part of India they want to explore
2. Duration — number of nights or days
3. Travel date or month — even approximate is fine
4. Group size — solo, couple, family, group
5. Budget range — optional, only ask if relevant
 
If the user mentions a non-India destination, gently redirect:
"We specialise in incredible India tours — from the golden deserts of Rajasthan to the backwaters of Kerala. Which part of India would you love to explore?"
 
RECOMMENDATIONS (trigger after destination + duration + one more detail collected):
- Transition into giving helpful, tailored suggestions based on what we have on this destination
- Reference package details naturally if available — otherwise speak from GeTS's general expertise
- Always offer to connect them with the GeTS team for a custom quote if exact pricing is unavailable
 
GROUNDING RULES (CRITICAL):
- Only answer using the context provided below — never fabricate prices, hotel names, or itinerary details
- PREVENT PREMATURE CONTEXT USAGE: During the info-gathering phase, NEVER mention specific numbers (like "3 nights", "₹45,000", "5 days") from the retrieved context as if they are facts or requirements. Only use generic enthusiasm until the Recommendation phase.
- If specific details are not available say: "We don't have that specific detail to hand right now — our team would love to put together a personalised quote for you"
- Never say "knowledge base", "database", or any system-internal term
 
FALLBACK HANDLING:
- If context is empty or irrelevant: "We'd love to help with that — our travel experts can put together something tailored for you. Would you like to share a few details so we can get started?"
- If completely off-topic: "We're best at helping you plan amazing India holidays! What destination are you dreaming of?"
- If user says goodbye or thanks: respond warmly and briefly — do not ask another question
- If user is frustrated or angry: acknowledge their feeling first, then respond helpfully
 
TOKEN EFFICIENCY:
- Be concise — never repeat what the user just said back to them word for word
- Never re-summarize the conversation so far
- Never explain what you are about to do — just do it
"""

async def generate_response(
    query: str,
    ranked_docs: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] = []
) -> str:
    """
    Generates a grounded, context-aware response using Gemini.
    
    Args:
        query: Current user message
        ranked_docs: Retrieved and ranked context documents
        conversation_history: List of previous turns [{"role": "user"/"assistant", "content": "..."}]
    
    Returns:
        Generated response string
    """
    
    start_time = time.time()

    # --- Build context block from ranked docs ---
    # Cap at top 2 chunks — more than this bloats the input and eats output token budget
    TOP_K_CHUNKS = 2
    MAX_WORDS_PER_CHUNK = 150

    if ranked_docs:
        context_parts = []
        for i, doc in enumerate(ranked_docs[:TOP_K_CHUNKS]):
            src = (doc.get("source") or "unknown").upper()
            conf = (doc.get("confidence") or "unknown").upper()
            answer = doc.get("answer", "").strip()

            # Trim each chunk to MAX_WORDS_PER_CHUNK to control input token usage
            words = answer.split()
            if len(words) > MAX_WORDS_PER_CHUNK:
                answer = " ".join(words[:MAX_WORDS_PER_CHUNK]) + "..."
                logger.warning(f"[GENERATION] Chunk {i+1} trimmed from {len(words)} to {MAX_WORDS_PER_CHUNK} words to save tokens")

            if answer:
                context_parts.append(f"[Source {i+1} | {src} | Confidence: {conf}]\n{answer}")

        context_text = "\n---\n".join(context_parts)
        logger.info(f"[GENERATION] Context built from {len(context_parts)} chunks (capped at {TOP_K_CHUNKS})")
    else:
        context_text = "No relevant context found."
        logger.warning("[GENERATION] No ranked docs provided — response will use fallback messaging")

    # --- Build conversation history string ---
    history_text = ""
    if conversation_history:
        history_lines = []
        for turn in conversation_history[-6:]:  # Last 6 turns max (3 exchanges) to control tokens
            role = "User" if turn.get("role") == "user" else "Assistant"
            content = turn.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines)
        logger.info(f"[GENERATION] Conversation history included: {len(conversation_history)} turns (capped at last 6)")
    else:
        logger.info("[GENERATION] No conversation history — treating as fresh conversation")

    # --- Assemble full prompt ---
    full_prompt = f"""{SYSTEM_PROMPT}

---
CONVERSATION SO FAR:
{history_text if history_text else "This is the start of the conversation."}

---
CONTEXT FROM KNOWLEDGE BASE:
{context_text}

---
CURRENT USER MESSAGE:
{query}

YOUR RESPONSE (write complete sentences only, do not stop mid-sentence):"""

    # --- Call Groq ---
    try:
        logger.info(f"[GENERATION] Sending request to Groq | Query: '{query}' | Docs: {len(ranked_docs)} | History turns: {len(conversation_history)}")
        
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT FROM KNOWLEDGE BASE:\n{context_text}\n\nCONVERSATION SO FAR:\n{history_text if history_text else 'This is the start of the conversation.'}\n\nCURRENT USER MESSAGE:\n{query}"}
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        
        response_text = response.choices[0].message.content.strip()
        finish_reason = response.choices[0].finish_reason
        elapsed = round(time.time() - start_time, 2)

        word_count = len(response_text.split())
        logger.info(f"[GENERATION] Response generated in {elapsed}s | Words: {word_count} | Finish reason: {finish_reason}")

        if word_count > 120:
            logger.warning(f"[GENERATION] Response exceeded expected length ({word_count} words) — review system prompt adherence")

        return response_text

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        logger.error(f"[GENERATION] Failed after {elapsed}s | Error: {str(e)}")
        logger.error(traceback.format_exc())
        return "I'm having trouble right now. Please try again or contact the GeTS team directly for assistance."


async def generate_response_stream(
    query: str,
    ranked_docs: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] = []
):
    """
    Streaming version of generate_response using Groq.
    """

    # --- Build context ---
    TOP_K_CHUNKS = 2
    MAX_WORDS_PER_CHUNK = 150

    if ranked_docs:
        context_parts = []
        for i, doc in enumerate(ranked_docs[:TOP_K_CHUNKS]):
            src_val = doc.get("source_url") or doc.get("source") or "unknown"
            src = str(src_val).upper()
            
            conf_val = doc.get("confidence")
            conf = str(conf_val).upper() if conf_val is not None else "UNKNOWN"
            
            answer = doc.get("answer") or doc.get("content") or ""
            answer = str(answer).strip()
            words = answer.split()
            if len(words) > MAX_WORDS_PER_CHUNK:
                answer = " ".join(words[:MAX_WORDS_PER_CHUNK]) + "..."
                logger.warning(f"[GENERATION] Stream chunk {i+1} trimmed from {len(words)} to {MAX_WORDS_PER_CHUNK} words")
            if answer:
                context_parts.append(f"[Source {i+1} | {src} | Confidence: {conf}]\n{answer}")
        context_text = "\n---\n".join(context_parts)
    else:
        context_text = "No relevant context found."
        logger.warning("[GENERATION] Stream: No ranked docs provided — response will use fallback messaging")

    # --- Build conversation history ---
    history_text = ""
    if conversation_history:
        history_lines = []
        for turn in conversation_history[-6:]:
            role = "User" if turn.get("role") == "user" else "Assistant"
            content = turn.get("content", "").strip()
            if content:
                history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines)

    # --- Stream from Groq ---
    try:
        logger.info(f"[GENERATION] Stream request to Groq | Query: '{query}' | Docs: {len(ranked_docs)}")

        stream = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT FROM KNOWLEDGE BASE:\n{context_text}\n\nCONVERSATION SO FAR:\n{history_text if history_text else 'This is the start of the conversation.'}\n\nCURRENT USER MESSAGE:\n{query}"}
            ],
            temperature=0.2,
            max_tokens=1024,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"[GENERATION] Stream failed | Error: {str(e)}")
        logger.error(traceback.format_exc())
        yield "I'm having trouble right now. Please try again or contact the GeTS team directly for assistance."