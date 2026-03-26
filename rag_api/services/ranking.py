from typing import List, Dict, Any

def rank_results(results: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Re-ranks documents prioritizing the Source of Truth hierarchy:
    1. Structured DB / Future System (Highest multiplier) -> Overrides old text
    2. High-Confidence IntelliTicks logs
    3. Medium/Low Confidence logs (Heavily penalized)
    """
    for doc in results:
        base_score = doc.get("score", 0.0)
        source = doc.get("source", "unknown")
        confidence = doc.get("confidence", "low")
        
        # Priority Multiplier Logic
        if source == "database":  # Future SQL/Supabase Integration Source
            doc["final_score"] = base_score * 2.0
            
        elif source == "intelliticks":
            if confidence == "high":
                doc["final_score"] = base_score * 1.5
            elif confidence == "medium":
                doc["final_score"] = base_score * 1.0
            else:
                # Disincentivize low confidence historical logs unless nothing else exists
                doc["final_score"] = base_score * 0.5
                
        else:
            doc["final_score"] = base_score
            
    # Sort descending by newly calculated final score
    ranked = sorted(results, key=lambda x: x["final_score"], reverse=True)
    return ranked[:top_k]
