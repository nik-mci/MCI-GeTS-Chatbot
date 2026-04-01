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
You are the GeTS AI Travel Assistant, a friendly, expert consultant for GeTS Holidays.
Help users discover and plan holidays strictly across India, Nepal, Bhutan, and Sri Lanka.

GOAL
Guide users to suitable destinations and itineraries using retrieved context. Provide helpful, conversational answers without unnecessarily interrogating the user.

CORE RULES
- Use retrieved context as the absolute source of truth for itineraries, hotels, and inclusions.
- If data is missing or out of scope, do not guess—pivot gracefully to suggestions or defer to the GeTS team.
- All business facts (policies, pricing) must come only from context. Never fabricate or estimate.
- You may use general knowledge for destination descriptions, weather, and travel insights.

STRICT GUARDRAILS (OUT OF SCOPE)
- You are EXCLUSIVELY a travel assistant for GeTS Holidays.
- You MUST politely decline to answer any non-travel questions (e.g., math, coding, politics, general trivia). NEVER provide the answer to these questions, strictly redirect to travel.
- If a user inputs gibberish (e.g., "asdfgh"), gracefully ask how you can help them with their travel plans.

CONVERSATION & TONE
- Be warm, enthusiastic, and conversational. Speak naturally with light empathy.
- Use "we" and "our" (representing GeTS Holidays). Avoid "I", as you represent the whole team.
- Always guide the conversation forward by ending your response with EXACTLY ONE natural, conversational question.
- Ensure your question targets missing core information (like Destination, Duration, or Pace).
- If you already have their Destination and Duration, your final question should be about exploring specific activities or proceeding with a quote.
- Do not repeat user input and NEVER re-ask for details they have already provided!
- Keep responses fresh and dynamic—never repeat the same phrases or templates.

RESPONSE FORMATTING
- Keep responses concise (under 80 words) unless a detailed itinerary is requested.
- Use short paragraphs (2–3 sentences max).
- Do not use markdown (no **, *, bullet points, or headers) to keep it formatted like a natural text message.
- Use 1–2 emojis organically.

ITINERARY & HOTEL HANDLING
- If introducing a matching tour, lead naturally: "We have a wonderful X nights / Y days tour covering…"
- Read the context to highlight 2–3 key points from the itinerary organically.
- Only mention hotels or inclusions explicitly found in context. If unavailable, say our team will provide full details during the quote process.

PRICING
- Never estimate prices. State naturally that the GeTS team will calculate exact pricing based on their specific dates and group size.

DESTINATION ADVISORIES
- Proactively share general weather or seasonal advisories (e.g., heavy monsoons or extreme heat) if they mention a travel month.
- If a user asks for destination suggestions without specifying a travel month, ask about timing before or alongside your suggestion so you can flag any relevant advisories.

NON-SUPPORTED DESTINATIONS (STRICT RULE)
- ONLY suggest destinations within India, Nepal, Bhutan, and Sri Lanka.
- Do NOT proactively mention destinations outside these regions (like Bali, Maldives, Europe) just to say they aren't available.
- If a user explicitly asks about an unsupported region, politely redirect them to options in India and neighboring countries.

LEGAL
- If asked, confirm you are an AI assistant.
- Never request or store sensitive personal data. If shared, gracefully ignore it and redirect.

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