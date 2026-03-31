"""One-shot script to migrate all data to Pinecone."""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services.ingestion import ingest_qa_pairs, ingest_scraped_pages, ingest_itineraries_docs
    print("--- Starting Pinecone Migration ---")
    ingest_qa_pairs(overwrite=False)   # overwrite=False since Pinecone doesn't support local clear
    ingest_scraped_pages()
    ingest_itineraries_docs()
    print("--- Migration Complete! ---")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
