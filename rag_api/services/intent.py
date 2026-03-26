from groq import AsyncGroq
import json
from models.schemas import IntentExtraction
from config import settings
import logging

logger = logging.getLogger(__name__)

# Configure Groq Client
client = AsyncGroq(
    api_key=settings.GROQ_API_KEY,
)

async def extract_intent_and_entities(query: str, history: list = None) -> IntentExtraction:
    """Uses LLM to extract structured travel entities and rebuilds a dense vector-optimized search string."""
    
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

    If a field is not present, set it to null (or empty array for destination). 
    Return ONLY valid, parsable JSON matching the exact schema requirements containing `rewritten_query`.
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Conversation History:\n{history}\n\nLatest User Query: {query}"}
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
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
        return IntentExtraction(intent="general", rewritten_query=query)
