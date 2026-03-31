from utils.vector_db import get_vector_db
from services.retrieval import retrieve_context
from models.schemas import IntentExtraction
import json

def debug_query(query, destination):
    intent = IntentExtraction(
        intent="itinerary",
        rewritten_query=query,
        destination=[destination]
    )
    
    results = retrieve_context(query, intent)
    
    output = []
    for r in results:
        output.append({
            "source": r.get('source'),
            "score": r.get('score'),
            "title": r.get('title'),
            "content": r.get('answer', r.get('content', ''))
        })
    
    with open("retrieval_debug_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Exported {len(results)} results to retrieval_debug_results.json")

if __name__ == "__main__":
    # Test for Golden Triangle
    test_query = "Can you show me a Golden Triangle itinerary?"
    print(f"\n--- Testing Retrieval for: '{test_query}' ---")
    debug_query(test_query, "Kerala")
