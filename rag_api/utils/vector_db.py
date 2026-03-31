import json
import os
import time
from typing import List, Dict, Any
import uuid
from pinecone import Pinecone
import google.generativeai as genai
from config import settings

# Configure Gemini for embeddings
genai.configure(api_key=settings.GEMINI_API_KEY)

class VectorDBBase:
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        pass
    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        pass
    def get_count(self) -> int:
        return 0

class PineconeDB(VectorDBBase):
    def __init__(self):
        self.model_name = settings.GEMINI_EMBEDDING_MODEL
        self.dimension = 768
            
        print(f"Connecting to Pinecone Index: {settings.PINECONE_INDEX_NAME} (Cloud-Native Gemini Embeddings)...")
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = pc.Index(settings.PINECONE_INDEX_NAME)

    def get_embedding(self, text: str) -> List[float]:
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_query"
            )
            return result['embedding']
        except Exception as e:
            print(f"Gemini Embedding failed: {e}")
            return [0.0] * self.dimension

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts: return
        
        try:
            # Batch embedding using Gemini with aggressive rate limit handling
            embeddings = []
            
            # Gemini Free Tier is very restrictive. Added more retries and longer delays.
            MAX_RETRIES = 10
            base_delay = 5
            
            for attempt in range(MAX_RETRIES):
                try:
                    result = genai.embed_content(
                        model=self.model_name,
                        content=texts,
                        task_type="retrieval_document"
                    )
                    embeddings = result['embedding']
                    break
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        delay = base_delay * (1.5 ** attempt) # Slightly slower growth
                        print(f"Rate limited. Attempt {attempt+1}/{MAX_RETRIES}. Waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        raise e
            
            if not embeddings:
                raise Exception("Failed to get embeddings after aggressive retries")

            vectors = []
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                clean_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    elif isinstance(v, list) and all(isinstance(i, str) for i in v):
                        clean_meta[k] = v
                    elif v is None:
                        clean_meta[k] = ""
                    else:
                        clean_meta[k] = json.dumps(v)
                        
                vector_id = str(uuid.uuid4())
                clean_meta['text'] = text
                vectors.append({"id": vector_id, "values": embeddings[i], "metadata": clean_meta})
                
            batch_size = 50 # Smaller batches for stability
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
                
            # mandatory sleep between batches for free tier stability
            time.sleep(3)
            print(f"Added {len(texts)} texts to Pinecone using Gemini.")
        except Exception as e:
            print(f"Failed to add texts to PineconeDB (Gemini): {e}")
            raise e

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query"
            )
            query_emb = result['embedding']
            
            response = self.index.query(
                vector=query_emb,
                top_k=k,
                include_metadata=True
            )
            
            results = []
            for match in response.matches:
                if match.metadata:
                    meta = match.metadata.copy()
                    meta['score'] = float(match.score)
                    results.append(meta)
            return results
        except Exception as e:
            print(f"Similarity search failed: {e}")
            return []

    def get_count(self) -> int:
        try:
            stats = self.index.describe_index_stats()
            return stats.get('total_vector_count', 0)
        except:
            return 0

def get_vector_db() -> VectorDBBase:
    # Always return PineconeDB for production/cloud-native
    return PineconeDB()
