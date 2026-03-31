import os
import sys
import json
from tqdm import tqdm

# Add the current directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings
from services.ingestion import ingest_qa_pairs, ingest_scraped_pages, ingest_itineraries_docs
from utils.vector_db import get_vector_db

def run_migration():
    print("🚀 Starting Cloud Migration (Supabase pgvector)...")
    
    # Initialize the new Supabase Vector DB
    # (The factory get_vector_db() now returns SupabaseDB)
    db = get_vector_db()
    
    # 1. Ingest QA Pairs
    if os.path.exists(settings.QA_PAIRS_PATH):
        print("\n📥 Ingesting QA pairs...")
        ingest_qa_pairs(settings.QA_PAIRS_PATH)
    else:
        print(f"\n⚠️ QA pairs file not found at {settings.QA_PAIRS_PATH}")

    # 2. Ingest Scraped Pages
    if os.path.exists(settings.SCRAPED_PAGES_PATH):
        print("\n📥 Ingesting scraped pages...")
        ingest_scraped_pages(settings.SCRAPED_PAGES_PATH)
    else:
        print(f"\n⚠️ Scraped pages file not found at {settings.SCRAPED_PAGES_PATH}")

    # 3. Ingest Itinerary Docs (DOCX)
    if os.path.exists(settings.ITINERARY_DOCS_PATH):
        print("\n📥 Ingesting itinerary documents...")
        ingest_itineraries_docs()
    else:
        print(f"\n⚠️ Itinerary docs directory not found at {settings.ITINERARY_DOCS_PATH}")

    print("\n✅ Migration to Supabase Complete!")
    print(f"Total Vectors in Supabase: {db.get_count()} (Note: count may be 0 if not implemented)")

if __name__ == "__main__":
    run_migration()
