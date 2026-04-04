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
        # Indian Regions & States (verified from getsholidays.com)
        "kerala", "rajasthan", "goa", "kashmir", "ladakh", "himachal", "himachal pradesh",
        "uttarakhand", "assam", "meghalaya", "arunachal", "arunachal pradesh",
        "karnataka", "tamil nadu", "gujarat", "maharashtra", "odisha",
        "punjab", "haryana", "madhya pradesh", "andaman",
        "north india", "south india", "northeast", "north east",

        # Cities & Key Landmarks (verified from getsholidays.com)
        "delhi", "agra", "jaipur", "jodhpur", "udaipur", "jaisalmer", "pushkar",
        "ranthambore", "varanasi", "haridwar", "rishikesh", "amritsar",
        "manali", "leh", "nubra valley", "pangong", "dharamshala",
        "mumbai", "goa", "kochi", "munnar", "rameshwaram", "madurai",
        "bangalore", "chennai", "orchha", "khajuraho", "hampi", "kaziranga",
        "golden triangle",

        # International (verified from getsholidays.com — India, Nepal, Bhutan, Sri Lanka only)
        "bhutan", "nepal", "sri lanka",
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
        "visa", "guide", "activities", "resort", "villa"
    ]
    
    MIN_TRAVEL_SIGNAL: int = 1

settings = Settings()
