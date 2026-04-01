from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    query: str
    user_context: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, str]]] = []

class IntentExtraction(BaseModel):
    destination: Optional[List[str]] = []
    budget: Optional[str] = None
    duration: Optional[str] = None
    travel_date: Optional[str] = None
    intent: str = "general" # pricing, booking, itinerary, general
    rewritten_query: str = "" # Optimized dense search format
    theme: Optional[str] = None # Theme extracted to help rewriting, optional

class SourceDocument(BaseModel):
    content: str
    metadata: Dict[str, Any]
    score: float # Similarity or assigned rank score

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    confidence: str
    metadata: IntentExtraction
