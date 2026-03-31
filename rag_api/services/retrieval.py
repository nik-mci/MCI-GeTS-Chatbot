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
        # Initialize score if not present (safety)
        if 'score' not in item:
            item['score'] = 0.1  # Low default fallback
            
        # 1. Destination Match/Mismatch Scoring
        if intent_data.destination:
            # Normalize to lowercase sets for efficient matching
            query_dests = set(d.lower() for d in intent_data.destination)
            doc_dests = set(d.lower() for d in item.get('destination', []))
            
            # Normalize common variations for strict matching
            def normalize_set(s):
                res = set()
                for i in s:
                    n = str(i).replace(" india", "").replace("india ", "").strip()
                    res.add(n)
                return res
            
            normalized_query = normalize_set(query_dests)
            normalized_doc = normalize_set(doc_dests)

            if normalized_query.intersection(normalized_doc):
                item['score'] *= 2.5  # Heavy boost for MATCH
                item['confidence'] = 'high'
            elif doc_dests: # Intent has destination, Doc has destination, but they DON'T match
                item['score'] *= 0.6  # Penalize MISMATCH
                
        # 2. Generic Phrase Penalty
        answer_text = str(item.get('answer', '')).lower()
        for pattern in settings.BAD_PATTERNS:
            if re.search(pattern, answer_text):
                item['score'] *= 0.4 # Heavy penalty for chatbot/system phrases
                break
                
        # 3. Pricing Intent Boost
        if intent_data.intent == 'pricing' and 'pricing' in item.get('tags', []):
            item['score'] *= 1.3
            
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
    
    # Step B: Increase retrieval depth to 50 to capture itineraries that might be semantically outranked by noise
    raw_results = db.similarity_search(search_string, k=50)
    
    # Step C: Filter and score adjust only if intent_data is provided
    if intent_data:
        adjusted_results = filter_by_metadata(raw_results, intent_data)
        # Re-sort based on new adjusted scores
        sorted_results = sorted(adjusted_results, key=lambda x: x.get('score', 0), reverse=True)
        return sorted_results[:10]  # Return top 10 high-quality results
    
    return raw_results[:10]
