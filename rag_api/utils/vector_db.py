import faiss
import numpy as np
import json
import os
import pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import uuid
from pinecone import Pinecone
from config import settings

class VectorDBBase:
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        pass
    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        pass
    def get_count(self) -> int:
        return 0

class FAISSDB(VectorDBBase):
    _model = None  # Class-level shared model to avoid reloading

    def __init__(self):
        self.index_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), settings.FAISS_INDEX_PATH))
        
        # Local Sentence Transformer Model (384 dimensions)
        self.model_name = 'all-MiniLM-L6-v2'
        self.dimension = 384
        
        if FAISSDB._model is None:
            print(f"Loading local embedding model: {self.model_name}...")
            FAISSDB._model = SentenceTransformer(self.model_name)
        
        self.index_file = os.path.join(self.index_path, "index.faiss")
        self.meta_file = os.path.join(self.index_path, "metadata.pkl")
        print(f"VectorDB initialized with path: {self.index_path}")
        
        if os.path.exists(self.index_file) and os.path.exists(self.meta_file):
            try:
                self.index = faiss.read_index(self.index_file)
                with open(self.meta_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                
                # Check dimensions consistency
                if self.index.d != self.dimension:
                    print(f"Dimension mismatch! Old: {self.index.d}, New: {self.dimension}. Starting fresh index.")
                    self._reset_index()
            except Exception as e:
                print(f"Error loading index: {e}. Starting fresh.")
                self._reset_index()
        else:
            self._reset_index()

    def _reset_index(self):
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []

    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding using local model."""
        try:
            return FAISSDB._model.encode(text).tolist()
        except Exception as e:
            print(f"Local Embedding failed: {e}")
            return [0.0] * self.dimension

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """Adds texts to the index using local embeddings (FAST)."""
        if not texts: return
        
        try:
            # Batch embedding (Local model handles this extremely fast)
            embeddings = FAISSDB._model.encode(texts)
            embeddings_np = np.array(embeddings).astype('float32')
            
            # normalize for cosine similarity
            faiss.normalize_L2(embeddings_np)
            self.index.add(embeddings_np)
            self.metadata.extend(metadatas)
            
            # Save
            os.makedirs(self.index_path, exist_ok=True)
            faiss.write_index(self.index, self.index_file)
            with open(self.meta_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            print(f"Added {len(texts)} texts. Total in index: {self.index.ntotal}")
        except Exception as e:
            print(f"Failed to add texts to VectorDB: {e}")
            raise e

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
            
        embeddings = FAISSDB._model.encode([query])
        query_emb = np.array(embeddings).astype('float32')
        faiss.normalize_L2(query_emb)
        
        distances, indices = self.index.search(query_emb, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.metadata):
                meta = self.metadata[idx].copy()
                meta['score'] = float(dist)
                results.append(meta)
        return results

    def get_count(self) -> int:
        return self.index.ntotal

class PineconeDB(VectorDBBase):
    _model = None

    def __init__(self):
        self.model_name = 'all-MiniLM-L6-v2'
        self.dimension = 384
        
        if PineconeDB._model is None:
            print(f"Loading local embedding model: {self.model_name}...")
            PineconeDB._model = SentenceTransformer(self.model_name)
            
        print(f"Connecting to Pinecone Index: {settings.PINECONE_INDEX_NAME}...")
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = pc.Index(settings.PINECONE_INDEX_NAME)

    def get_embedding(self, text: str) -> List[float]:
        try:
            return PineconeDB._model.encode(text).tolist()
        except Exception as e:
            print(f"Local Embedding failed: {e}")
            return [0.0] * self.dimension

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts: return
        
        try:
            embeddings = PineconeDB._model.encode(texts).tolist()
            
            vectors = []
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                # Ensure metadata values are strings, ints, floats, or lists of strings
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
                
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
                
            print(f"Added {len(texts)} texts to Pinecone.")
        except Exception as e:
            print(f"Failed to add texts to PineconeDB: {e}")
            raise e

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        query_emb = PineconeDB._model.encode([query]).tolist()[0]
        
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

    def get_count(self) -> int:
        stats = self.index.describe_index_stats()
        return stats.get('total_vector_count', 0)

# Expose a factory pattern making it easy to swap implementations
def get_vector_db() -> VectorDBBase:
    if settings.PINECONE_API_KEY:
        return PineconeDB()
    return FAISSDB()
