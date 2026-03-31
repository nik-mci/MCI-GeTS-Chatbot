import json
import os
import time
from typing import List, Dict, Any
import uuid
import vecs
import google.generativeai as genai
import numpy as np
from config import settings

# FastEmbed import (will be installed via requirements.txt)
try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

# Configure Gemini for LLM part (still used for chat)
genai.configure(api_key=settings.GEMINI_API_KEY)

class VectorDBBase:
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        pass
    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        pass
    def get_count(self) -> int:
        return 0

class SupabaseDB(VectorDBBase):
    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        
        if self.provider == "fastembed":
            if TextEmbedding is None:
                raise ImportError("fastembed is not installed. Please run pip install fastembed")
            print(f"🚀 Initializing FastEmbed ({settings.FASTEMBED_MODEL})...")
            self.model = TextEmbedding(model_name=settings.FASTEMBED_MODEL)
            # BAAI/bge-small-en-v1.5 and all-MiniLM-L6-v2 are 384D
            self.dimension = 384
        else:
            self.model_name = settings.GEMINI_EMBEDDING_MODEL
            self.dimension = 3072  # Default for Gemini text-embedding-004
            
        self.collection_name = "gets_travel_vectors"
        
        print(f"Connecting to Supabase (pgvector) Collection: {self.collection_name}...")
        self.vx = vecs.create_client(settings.SUPABASE_CONNECTION_STRING)
        
        try:
            self.collection = self.vx.get_or_create_collection(
                name=self.collection_name, 
                dimension=self.dimension
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                print(f"⚠️ Dimension mismatch detected ({self.dimension}). Recreating collection '{self.collection_name}'...")
                self.vx.delete_collection(self.collection_name)
                self.collection = self.vx.get_or_create_collection(
                    name=self.collection_name, 
                    dimension=self.dimension
                )
            else:
                raise e

    def get_embedding(self, text: str) -> List[float]:
        try:
            if self.provider == "fastembed":
                # FastEmbed returns a generator of numpy arrays
                embeddings = list(self.model.embed([text]))
                return embeddings[0].tolist()
            else:
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="retrieval_query"
                )
                return result['embedding']
        except Exception as e:
            print(f"Embedding failed ({self.provider}): {e}")
            return [0.0] * self.dimension

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts: return
        
        try:
            embeddings = []
            if self.provider == "fastembed":
                # Local fast embedding (no rate limits!)
                print(f"Embedding batch of {len(texts)} using FastEmbed...")
                embeddings = list(self.model.embed(texts))
                # Convert np.ndarrays to lists
                embeddings = [e.tolist() for e in embeddings]
            else:
                # Gemini Cloud fallback
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
                            delay = base_delay * (1.5 ** attempt)
                            print(f"Rate limited (Gemini). Attempt {attempt+1}/{MAX_RETRIES}. Waiting {delay:.1f}s...")
                            time.sleep(delay)
                        else:
                            raise e
            
            if not embeddings:
                raise Exception(f"Failed to get embeddings ({self.provider})")

            records = []
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                clean_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    elif isinstance(v, list) and all(isinstance(idx, str) for idx in v):
                        clean_meta[k] = v
                    elif v is None:
                        clean_meta[k] = ""
                    else:
                        clean_meta[k] = json.dumps(v)
                        
                vector_id = str(uuid.uuid4())
                clean_meta['text'] = text
                records.append((vector_id, embeddings[i], clean_meta))
                
            self.collection.upsert(records=records)
            print(f"✅ Added {len(texts)} texts to Supabase.")
        except Exception as e:
            print(f"Failed to add texts to SupabaseDB: {e}")
            raise e

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        try:
            query_emb = self.get_embedding(query)
            
            response = self.collection.query(
                data=query_emb,
                limit=k,
                include_metadata=True,
                measure="cosine_distance"
            )
            
            results = []
            for item in response:
                # vecs query returns [(id, metadata, distance), ...]
                if isinstance(item, tuple) and len(item) >= 3:
                    meta = item[1].copy()
                    # Convert cosine distance to a similarity score (1 - distance)
                    # Ensuring it stays within [0, 1] range
                    distance = item[2]
                    score = max(0.0, 1.0 - float(distance))
                    meta['score'] = score
                    results.append(meta)
            return results
        except Exception as e:
            print(f"Similarity search failed: {e}")
            return []

    def get_count(self) -> int:
        try:
            import psycopg2
            conn = psycopg2.connect(settings.SUPABASE_CONNECTION_STRING)
            with conn.cursor() as cur:
                cur.execute(f'SELECT count(*) FROM vecs."{self.collection_name}"')
                count = cur.fetchone()[0]
                conn.close()
                return count
        except Exception as e:
            print(f"Failed to get vector count: {e}")
            return 0

def get_vector_db() -> VectorDBBase:
    return SupabaseDB()
