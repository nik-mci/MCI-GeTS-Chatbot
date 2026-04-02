import json
import os
import traceback
import time
from typing import List, Dict, Any
import uuid
import vecs
import google.generativeai as genai
import numpy as np
from config import settings

# Configure Logging
import logging
import threading

logger = logging.getLogger(__name__)

# Module-level configuration for Singleton
_db_instance = None
_db_lock = threading.Lock()

# Embedding imports — fastembed preferred (ONNX, small), sentence-transformers as fallback
try:
    from fastembed import TextEmbedding as FastEmbedding
except ImportError:
    FastEmbedding = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

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
        
        if self.provider in ("fastembed", "sentence-transformers"):
            if FastEmbedding is not None:
                print(f"Initializing FastEmbed ({settings.FASTEMBED_MODEL})...")
                self.model = FastEmbedding(model_name=settings.FASTEMBED_MODEL)
                self._use_fastembed = True
            elif SentenceTransformer is not None:
                print(f"Initializing SentenceTransformer ({settings.FASTEMBED_MODEL})...")
                self.model = SentenceTransformer(settings.FASTEMBED_MODEL)
                self._use_fastembed = False
            else:
                raise ImportError("Neither fastembed nor sentence-transformers is installed.")
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
            
            # Ensure cosine distance index exists for fast and accurate similarity matching
            try:
                logger.info(f"Ensuring cosine distance index exists for {self.collection_name}...")
                self.collection.create_index(measure=vecs.IndexMeasure.cosine_distance)
            except Exception as index_e:
                logger.info(f"Index check complete (it likely already exists): {index_e}")
                
        except Exception as e:
            if "dimension" in str(e).lower():
                print(f"⚠️ Dimension mismatch detected ({self.dimension}). Recreating collection '{self.collection_name}'...")
                self.vx.delete_collection(self.collection_name)
                self.collection = self.vx.get_or_create_collection(
                    name=self.collection_name, 
                    dimension=self.dimension
                )
                self.collection.create_index(measure=vecs.IndexMeasure.cosine_distance)
            else:
                raise e

    def get_embedding(self, text: str) -> List[float]:
        try:
            if self.provider in ("fastembed", "sentence-transformers"):
                if self._use_fastembed:
                    return list(self.model.embed([text]))[0].tolist()
                return self.model.encode(text).tolist()
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
            if self.provider in ("fastembed", "sentence-transformers"):
                if self._use_fastembed:
                    print(f"Embedding batch of {len(texts)} using FastEmbed...")
                    embeddings = [e.tolist() for e in self.model.embed(texts)]
                else:
                    print(f"Embedding batch of {len(texts)} using SentenceTransformer...")
                    embeddings = [e.tolist() for e in self.model.encode(texts)]
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
            print(f"Added {len(texts)} texts to Supabase.")
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
                include_value=True,
                measure="cosine_distance"
            )
            
            results = []
            for item in response:
                if len(item) >= 2:
                    meta = {}
                    distance = 0.0
                    
                    # vecs versions differ: can be (id, distance, meta) or (id, meta, distance)
                    if len(item) == 3:
                        if isinstance(item[1], dict):
                            meta = item[1].copy()
                            distance = float(item[2])
                        elif isinstance(item[2], dict):
                            meta = item[2].copy()
                            distance = float(item[1])
                    elif len(item) == 2:
                        if isinstance(item[1], dict):
                            meta = item[1].copy()
                    
                    score = max(0.0, 1.0 - distance)
                    meta['score'] = score
                    results.append(meta)
            return results
        except Exception as e:
            logger.error(f"❌ [DATABASE] Similarity search failed: {e}")
            logger.error(traceback.format_exc())
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
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = SupabaseDB()
    return _db_instance
