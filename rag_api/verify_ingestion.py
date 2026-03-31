import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.vector_db import get_vector_db
from services.intent import IntentExtraction

def verify_ingestion():
    db = get_vector_db()
    print(f"Total items in index: {db.index.ntotal}")
    
    # Search for something unique to the new itineraries
    query = "Andaman tour itinerary"
    intent = IntentExtraction(
        intent="itinerary",
        rewritten_query="itinerary for Best of Andaman tour",
        destination=["Andaman"]
    )
    
    results = db.similarity_search(query, k=5)
    print(f"\nSearch results for '{query}':")
    for r in results:
        source = r.get('source', 'unknown')
        title = r.get('title', 'unknown')
        print(f"- [{source}] {title} (Score: {r.get('score'):.4f})")
        # Check if it's from the new itineraries
        if r.get('type') == 'itinerary_doc':
             print("  [CONFIRMED] Found new itinerary document content.")

if __name__ == "__main__":
    verify_ingestion()
