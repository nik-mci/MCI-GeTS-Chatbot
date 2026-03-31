from utils.vector_db import get_vector_db
import json

def find_itineraries():
    db = get_vector_db()
    print(f"Total in index: {db.index.ntotal}")
    
    # Search for anything mentioning "North East" or "Kolkata" and check sources
    ne_chunks = []
    for meta in db.metadata:
        if not meta: continue
        source = str(meta.get("source") or "").lower()
        content = str(meta.get("content") or meta.get("answer") or "").lower()
        title = str(meta.get("title") or "").lower()
        
        if "north east" in content or "north east" in title or "delightful north-east" in source:
            ne_chunks.append(meta)
            
    print(f"Found {len(ne_chunks)} potential North East chunks.")
    
    # Group by source
    sources = {}
    for chunk in ne_chunks:
        src = chunk.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        
    print("\nSources distribution:")
    for src, count in sources.items():
        print(f" - {src}: {count} chunks")
        
    # Sample a chunk from the Word doc to see if it's day-by-day
    for chunk in ne_chunks:
        if str(chunk.get("source", "")).endswith(".docx"):
            print("\nSample chunk from Docx:")
            print(f"Source: {chunk.get('source')}")
            content_val = chunk.get('content') or chunk.get('answer') or ""
            print(f"Content: {content_val[:500]}...")
            break

if __name__ == "__main__":
    find_itineraries()
