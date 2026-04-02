import os
from pydantic_settings import BaseSettings

_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "fastembed")
    FASTEMBED_MODEL: str = os.getenv("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    FAISS_INDEX_PATH: str = "faiss_index"
    QA_PAIRS_PATH: str = "../output/qa_pairs.json"
    SCRAPED_PAGES_PATH: str = "../data/raw/scraped_pages.json"
    ITINERARY_DOCS_PATH: str = "../GeTS Itineraries"

    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_CONNECTION_STRING: str = os.getenv("SUPABASE_CONNECTION_STRING", "")

    # Vector DB Support
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "gets-travel-index")

    model_config = {
        "env_file": _env_file,
        "extra": "ignore"
    }

    # Data Quality
    KNOWN_DESTINATIONS: list = [
        # Regional/State (India)
        "kerala", "rajasthan", "goa", "kashmir", "ladakh", "himachal", "uttarakhand",
        "sikkim", "assam", "meghalaya", "arunachal", "nagaland", "manipur", "mizoram", "tripura",
        "karnataka", "tamil nadu", "andhra pradesh", "telangana", "gujarat", "maharashtra", 
        "west bengal", "odisha", "punjab", "haryana", "uttar pradesh", "madhya pradesh", "andaman",
        "north india", "south india", "east india", "west india", "central india", "north east", "northeast",
        
        # Cities & Key Landmarks
        "delhi", "agra", "jaipur", "jodhpur", "udaipur", "pushkar", "ranthambore", "varanasi", 
        "rishikesh", "mathura", "vrindavan", "orchha", "khajuraho", "mumbai", "amritsar", 
        "hampi", "kaziranga", "leh", "dharamshala", "golden triangle",
        
        # International
        "bhutan", "nepal", "sri lanka", "bali", "dubai", "maldives", "switzerland", "thailand", "europe",
        "vietnam", "cambodia", "laos", "turkey", "egypt", "greece"
    ]
    
    BAD_PATTERNS: list = [
        r"connect you to",
        r"share your (details|contact)",
        r"no one is available",
        r"leave your message",
        r"we will get back",
        r"our team will contact",
        r"please provide (name|email|phone)",
        r"awesome! in this tour, discover",
        r"may i have your name please",
        r"how many adults will be joining",
        r"gets holidays helps you explore more",
        r"if you want india tour i can help",
        r"you want (.*) tour from (.*)\? right"
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
