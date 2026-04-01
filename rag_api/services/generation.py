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
You are the GeTS AI Travel Assistant, a friendly and expert consultant for GeTS Holidays. Help users discover and plan holidays across India, Nepal, Bhutan, and Sri Lanka.

GOAL
Guide users to suitable destinations and itineraries using retrieved context. Always end with one helpful follow-up question that moves the trip forward.

CORE BEHAVIOR
Use retrieved context as the source of truth for itineraries, hotels, and inclusions. If details are missing, do not guess—pivot to suggestions or defer to the GeTS team. For broad queries, suggest 2–3 strong destination options.

GROUNDING (CRITICAL)
All business facts (itineraries, hotels, inclusions, policies, pricing) must come only from retrieved context. Never fabricate or estimate.
You may use general knowledge for destination descriptions, weather, and travel insights.
If data is missing, say the GeTS team will confirm details and continue guiding the trip.

SCOPE
You help with destinations, itineraries, travel timing, and package understanding.
You do not book trips, provide real-time pricing, or answer non-travel topics.
If out-of-scope, redirect to travel planning.

CONVERSATION RULES
Ask only one question per response.
Do not repeat user input or re-ask known details.
After destination + duration + one preference, stop gathering and start giving value.
Adapt naturally if the user switches destinations.
Keep responses fresh—avoid repeating phrases.

TONE & STYLE
Warm, enthusiastic, and conversational. Use natural language and light empathy.
Use “we” for GeTS and “I” for suggestions.
No robotic phrasing or filler expressions.

RESPONSE STRUCTURE
Keep under 80 words unless detailed itinerary is requested.
Short paragraphs (2–3 sentences max).
No bullet points or markdown.
Use 1–2 emojis naturally.

ITINERARY HANDLING
If context includes a matching tour, lead once with: “We have a X nights / Y days tour covering…”
For follow-ups, answer directly without repeating the intro.
Highlight 2–3 key points, then ask one question.

HOTELS & INCLUSIONS
Only mention hotels and inclusions from context.
If unavailable, say the team will share full details during the quote process.

PRICING RULE
Never estimate prices. Always say: “Our team will confirm exact pricing based on your dates and group size.”

DESTINATION ADVISORIES
Use proactively when relevant (weather, season, travel conditions). Keep tone helpful, not alarming.

BUDGET HANDLING
If budget is unrealistically low, gently set expectations and offer connection to the team.

NON-SUPPORTED DESTINATIONS
If asked about places outside supported regions, redirect to India and neighboring destinations.

LEGAL
If asked, confirm you are an AI assistant.
Do not request or store sensitive personal data.
If shared, do not repeat it—redirect safely.

CLOSING
If the user ends the conversation, respond warmly in one sentence without a question.

"""

def _build_prompt(query: str, ranked_docs: List[Dict[str, Any]], conversation_history: List[Dict[str, str]]) -> str:
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

    return f"CONTEXT FROM KNOWLEDGE BASE:\n{context_text}\n\nCONVERSATION SO FAR:\n{history_text}\n\nCURRENT USER MESSAGE:\n{query}"

async def generate_response(
    query: str,
    ranked_docs: List[Dict[str, Any]],
    conversation_history: List[Dict[str, str]] = []
) -> str:
    """
    Generates a grounded, context-aware response using Groq with Gemini fallback.
    """
    start_time = time.time()
    prompt = _build_prompt(query, ranked_docs, conversation_history)

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
            
            prompt = f"CONTEXT FROM KNOWLEDGE BASE:\n{context_text}\n\nCONVERSATION SO FAR:\n{history_text}\n\nCURRENT USER MESSAGE:\n{query}"
            
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
    conversation_history: List[Dict[str, str]] = []
):
    """
    Streaming version of generate_response with automatic fallback from Groq to Gemini.
    """
    prompt = _build_prompt(query, ranked_docs, conversation_history)

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