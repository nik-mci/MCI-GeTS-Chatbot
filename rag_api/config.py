import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME: str = "gemini-flash-latest"
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    FAISS_INDEX_PATH: str = "faiss_index"
    QA_PAIRS_PATH: str = "../output/qa_pairs.json"
    SCRAPED_PAGES_PATH: str = "../data/raw/scraped_pages.json"
    
    # Future DB support
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

    # Data Quality
    KNOWN_DESTINATIONS: list = ["bali", "dubai", "maldives", "switzerland", "thailand", "europe"]
    
    BAD_PATTERNS: list = [
        r"connect you to",
        r"share your (details|contact)",
        r"no one is available",
        r"leave your message",
        r"we will get back",
        r"our team will contact",
        r"please provide (name|email|phone)"
    ]
    
    LEAD_CAPTURE_PATTERNS: list = [
        r"contact you",
        r"share (your|his|her) details",
        r"provide (your|his|her) (number|phone|email)",
        r"callback",
        r"reach out to you"
    ]
    
    CONVERSATION_FILLER_PATTERNS: list = [
        r"great!",
        r"thanks",
        r"ok",
        r"noted",
        r"which package would you like",
        r"let me check"
    ]
    
    GENERIC_MARKETING_PATTERNS: list = [
        r"we can customize",
        r"we offer",
        r"best experience",
        r"tailored for you",
        r"dream holiday",
        r"expert team"
    ]
    
    TRAVEL_KEYWORDS: list = [
        "package", "itinerary", "days", "nights",
        "price", "cost", "inclusion", "exclusion",
        "hotel", "flight", "transfer", "stay",
        "destination", "tour", "trip", "budget",
        "bali", "maldives", "dubai", "switzerland", "thailand", "europe",
        "visa", "guide", "activities", "resort", "villa"
    ]
    
    MIN_TRAVEL_SIGNAL: int = 1

settings = Settings()
