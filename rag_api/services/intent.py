import google.generativeai as genai
from groq import Groq
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from config import settings

logger = logging.getLogger(__name__)

# Initialize Groq Client
client = Groq(api_key=settings.GROQ_API_KEY)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

from models.schemas import IntentExtraction

async def extract_intent_and_entities(query: str, history: list = None) -> IntentExtraction:
    """Uses Gemini to extract structured travel entities and rebuilds a dense vector-optimized search string."""
    
    # Format history for the prompt
    history_str = ""
    if history:
        for msg in history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            history_str += f"{role}: {content}\n"

    system_prompt = f"""
    You are an intelligent query parser for a travel company chatbot retrieval engine.
    Extract the following entities if present in the user query:
    - destination (array of strings, e.g. ["Delhi", "Agra"])
    - budget (string, e.g. "$5000", "cheap")
    - duration (string, e.g. "5 days", "1 week")
    - travel_date (string, e.g. "Next month", "December 2026")
    - intent (enum: pricing, booking, itinerary, general)
    
    CRITICAL INSTRUCTION - BROAD THEMES:
    If a user asks for a theme (Family, Honeymoon, Adventure, Luxury, Wildlife) WITHOUT a destination:
    1. Set destination to an empty array [].
    2. Rewrite the query to target typical "best-of" or "popular" packages for that theme.
    Example: "Family trip 👨‍👩‍👧‍👧" -> "popular family tour packages and itineraries in India and beyond"
    Example: "Honeymoon 💑" -> "romantic honeymoon packages with luxury stays and private tours"

    Return ONLY valid, parsable JSON matching the schema.
    """
    
    try:
        prompt = f"Conversation History:\n{history_str}\n\nLatest User Query: {query}"

        # --- Attempt 1: Groq ---
        try:
            logger.info("🧠 [INTENT] Attempting extraction with Groq...")
            
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}, # Force JSON mode
                temperature=0,
            )
            
            data = json.loads(response.choices[0].message.content)
            logger.info("✅ [INTENT] Groq extraction success.")

        except Exception as groq_err:
            logger.warning(f"⚠️ [INTENT] Groq failed: {groq_err}. Falling back to Gemini...")
            
            # --- Attempt 2: Gemini Fallback ---
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=system_prompt
            )
            
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0,
                    response_mime_type="application/json",
                )
            )
            
            data = json.loads(response.text)
            logger.info("✨ [INTENT] Gemini Fallback extraction success.")
        
        # Ensure it matches our IntentExtraction model
        extracted_intent = IntentExtraction(**data)
        
        # Fallback: Deterministic Destination Extraction if LLM misses it
        if not extracted_intent.destination:
            from services.ingestion import extract_destinations
            extracted_intent.destination = extract_destinations(query)
            if extracted_intent.destination:
                logger.info(f"Fallback destination detection found: {extracted_intent.destination}")
        
        return extracted_intent

    except Exception as e:
        logger.error(f"❌ [INTENT] All extraction attempts failed: {e}")
        # Return fallback neutral intent and raw query if extraction fails entirely
        return IntentExtraction(intent="general", rewritten_query=query, destination=[])
