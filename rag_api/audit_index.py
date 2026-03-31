from utils.vector_db import get_vector_db
import json

def audit_index():
    db = get_vector_db()
    print(f"Total in index: {db.index.ntotal}")
    
    print(f"--- Meta for Rank 1 ---")
    meta = db.metadata[0]
    print(f"Destination Tags: {meta.get('destination')}")
    print(f"Source: {meta.get('source')}")

if __name__ == "__main__":
    audit_index()
