import json
import os
import time
from typing import List, Dict, Any
import uuid
import vecs
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

class SupabaseDB(VectorDBBase):
    def __init__(self):
        self.model_name = settings.GEMINI_EMBEDDING_MODEL
        self.dimension = 768
        self.collection_name = "gets_travel_vectors"
        
        print(f"Connecting to Supabase (pgvector) Collection: {self.collection_name}...")
        # create_client takes the connection string
        self.vx = vecs.create_client(settings.SUPABASE_CONNECTION_STRING)
        self.collection = self.vx.get_or_create_collection(
            name=self.collection_name, 
            dimension=self.dimension
        )

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
                        print(f"Rate limited. Attempt {attempt+1}/{MAX_RETRIES}. Waiting {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        raise e
            
            if not embeddings:
                raise Exception("Failed to get embeddings after aggressive retries")

            records = []
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
                records.append((vector_id, embeddings[i], clean_meta))
                
            # vecs upsert handles records list
            self.collection.upsert(records=records)
                
            # mandatory sleep between batches for free tier stability
            time.sleep(3)
            print(f"Added {len(texts)} texts to Supabase.")
        except Exception as e:
            print(f"Failed to add texts to SupabaseDB (Gemini): {e}")
            raise e

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query"
            )
            query_emb = result['embedding']
            
            # vecs query method
            response = self.collection.query(
                data=query_emb,
                limit=k,
                include_metadata=True,
                measure="cosine_distance"
            )
            
            results = []
            for item in response:
                if isinstance(item, tuple) and len(item) >= 2:
                    meta = item[1].copy()
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
