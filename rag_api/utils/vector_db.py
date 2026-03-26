import faiss
import numpy as np
import json
import os
from typing import List, Dict, Any
import pickle

# We use sentence-transformers locally for 100% free embeddings as Deepseek focuses on chat completions.
from sentence_transformers import SentenceTransformer

from config import settings

class VectorDBBase:
    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        pass
    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        pass

class FAISSDB(VectorDBBase):
    def __init__(self):
        self.index_path = settings.FAISS_INDEX_PATH
        self.dimension = 384  # Standard dense dimension for all-MiniLM-L6-v2
        
        # Free-tier fast local embeddings
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
        self.index_file = f"{self.index_path}/index.faiss"
        self.meta_file = f"{self.index_path}/metadata.pkl"
        
        if os.path.exists(self.index_file) and os.path.exists(self.meta_file):
            self.index = faiss.read_index(self.index_file)
            with open(self.meta_file, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []

    def get_embedding(self, text: str) -> List[float]:
        emb = self.encoder.encode([text])[0]
        return emb.tolist()

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts: return
        embeddings = []
        for text in texts:
            embeddings.append(self.get_embedding(text))
            
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

    def similarity_search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
            
        query_emb = np.array([self.get_embedding(query)]).astype('float32')
        faiss.normalize_L2(query_emb)
        
        distances, indices = self.index.search(query_emb, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1:
                meta = self.metadata[idx].copy()
                meta['score'] = float(dist)
                results.append(meta)
        return results

# Expose a factory pattern making it easy to swap implementations
def get_vector_db() -> VectorDBBase:
    return FAISSDB()
