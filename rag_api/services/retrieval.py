from utils.vector_db import get_vector_db
from models.schemas import IntentExtraction
from typing import List, Dict, Any
from config import settings
import re

db = get_vector_db()

def filter_by_metadata(items: List[Dict[str, Any]], intent_data: IntentExtraction) -> List[Dict[str, Any]]:
    """Filters and dynamically adjust scores based on extracted intents and metadata."""
    filtered = []
    for item in items:
        # 1. Destination Match/Mismatch Scoring
        if intent_data.destination:
            # Normalize to lowercase sets for efficient matching
            query_dests = set(d.lower() for d in intent_data.destination)
            # Use the new 'destination' metadata field added during ingestion
            doc_dests = set(d.lower() for d in item.get('destination', []))
            
            if query_dests.intersection(doc_dests):
                item['score'] *= 2.0  # Boost MATCH
                item['confidence'] = 'high'
            elif doc_dests: # Intent has destination, Doc has destination, but they DON'T match
                item['score'] *= 0.7  # Penalize MISMATCH
                
        # 2. Generic Phrase Penalty
        answer_text = item.get('answer', '').lower()
        for pattern in settings.BAD_PATTERNS:
            if re.search(pattern, answer_text):
                item['score'] *= 0.5 # Heavy penalty for chatbot/system phrases
                break
                
        # 3. Pricing Intent Boost (Keep existing)
        if intent_data.intent == 'pricing' and 'pricing' in item.get('tags', []):
            item['score'] *= 1.2
            
        # 4. Hard Filter (Safety Safeguard)
        hard_bad_patterns = settings.LEAD_CAPTURE_PATTERNS
        is_hard_rejected = False
        for pattern in hard_bad_patterns:
            if re.search(pattern, answer_text):
                is_hard_rejected = True
                break
        
        if not is_hard_rejected:
            filtered.append(item)
            
    return filtered

def retrieve_context(query: str, intent_data: IntentExtraction = None) -> List[Dict[str, Any]]:
    """Retrieves context using semantic search and applies business logic filters."""
    # Step A: Use Rewritten Query if available for accuracy, else fallback to raw query
    search_string = query
    if intent_data and intent_data.rewritten_query:
        search_string = intent_data.rewritten_query
    
    # Step B: Restrict raw retrieval down to 10 for latency and noise limits
    raw_results = db.similarity_search(search_string, k=10)
    
    # Step C: Filter and score adjust only if intent_data is provided
    if intent_data:
        return filter_by_metadata(raw_results, intent_data)
    
    return raw_results
