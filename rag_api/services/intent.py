# import google.generativeai as genai
from groq import Groq
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from config import settings

logger = logging.getLogger(__name__)

# Initialize Groq Client
client = Groq(api_key=settings.GROQ_API_KEY)

# Configure Gemini (Commented out)
# genai.configure(api_key=settings.GEMINI_API_KEY)

from models.schemas import IntentExtraction

async def extract_intent_and_entities(query: str, history: list = None) -> IntentExtraction:
    """Uses Gemini to extract structured travel entities and rebuilds a dense vector-optimized search string."""
    
    system_prompt = """
    You are an intelligent query parser for a travel company chatbot retrieval engine.
    Extract the following entities if present in the user query:
    - destination (array of strings, e.g. ["Delhi", "Agra"])
    - budget (string, e.g. "$5000", "cheap")
    - duration (string, e.g. "5 days", "1 week")
    - travel_date (string, e.g. "Next month", "December 2026")
    - intent (enum: pricing, booking, itinerary, general)
    
    CRITICAL INSTRUCTION - REWRITTEN QUERY:
    Generate an optimal search engine query from the user's intent. 
    Make it highly dense and descriptive ignoring conversational filler.
    Example Input: "I want a cheap bali trip" -> Output: "budget Bali tour packages with itinerary and pricing"

    Return ONLY valid, parsable JSON matching the schema.
    """
    
    try:
        # --- Groq Implementation ---
        prompt = f"Conversation History:\n{history}\n\nLatest User Query: {query}"
        
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

        # --- Original Gemini Implementation (Commented) ---
        """
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_prompt
        )
        
        prompt = f"Conversation History:\n{history}\n\nLatest User Query: {query}"
        
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
            )
        )
        
        data = json.loads(response.text)
        """
        
        # Ensure it matches our IntentExtraction model
        extracted_intent = IntentExtraction(**data)
        
        # Fallback: Deterministic Destination Extraction if Gemini misses it
        if not extracted_intent.destination:
            from services.ingestion import extract_destinations
            extracted_intent.destination = extract_destinations(query)
            if extracted_intent.destination:
                logger.info(f"Fallback destination detection found: {extracted_intent.destination}")
        
        return extracted_intent

    except Exception as e:
        logger.error(f"Intent extraction failed: {e}")
        # Return fallback neutral intent and raw query if extraction fails entirely
        return IntentExtraction(intent="general", rewritten_query=query, destination=[])
