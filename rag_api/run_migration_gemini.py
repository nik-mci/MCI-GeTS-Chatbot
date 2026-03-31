import sys
import os
import traceback

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services.ingestion import ingest_qa_pairs, ingest_scraped_pages, ingest_itineraries_docs
    print("--- Starting Gemini Cloud Migration (768D) ---")
    
    # Re-ingest everything to the new 768D index
    # Note: ingest_qa_pairs(overwrite=True) will just proceed with adding texts since FAISS is gone
    ingest_qa_pairs(overwrite=True)
    ingest_scraped_pages()
    ingest_itineraries_docs()
    
    print("--- Gemini Cloud Migration Complete! ---")
    
    from utils.vector_db import get_vector_db
    db = get_vector_db()
    print(f"Total Vectors in 768D Index: {db.get_count()}")

except Exception as e:
    traceback.print_exc()
    sys.exit(1)
