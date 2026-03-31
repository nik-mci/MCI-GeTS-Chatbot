from utils.vector_db import get_vector_db
import json
import numpy as np
import faiss

def deep_audit(query):
    db = get_vector_db()
    
    # 1. Get raw top 100
    embeddings = db._model.encode([query])
    query_emb = np.array(embeddings).astype('float32')
    faiss.normalize_L2(query_emb)
    
    distances, indices = db.index.search(query_emb, 100)
    
    print(f"--- Top 100 Raw Results for: '{query}' ---")
    found_itinerary_count = 0
    
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx == -1: continue
        meta = db.metadata[idx]
        source = meta.get('source')
        is_itinerary = source and source.endswith('.docx')
        
        if is_itinerary:
            found_itinerary_count += 1
            print(f"Rank {rank+1:02} | Score: {dist:.4f} | Source: {source} | Content: {meta.get('answer')[:100]}...")
            
    if found_itinerary_count == 0:
        print("No itineraries found in top 100!")
    else:
        print(f"\nFound {found_itinerary_count} itineraries in top 100.")

if __name__ == "__main__":
    deep_audit("Sikkim tour itinerary")
