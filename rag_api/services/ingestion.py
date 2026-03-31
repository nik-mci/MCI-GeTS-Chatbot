import sys
import os
import json
import logging
import re
from docx import Document
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.vector_db import get_vector_db
from config import settings

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

logger = logging.getLogger(__name__)

def extract_destinations(text: str) -> list:
    """Deterministic destination extraction with normalization."""
    text_normalized = text.lower().replace("-", " ")
    found = []
    for d in settings.KNOWN_DESTINATIONS:
        # Match as whole word or part of hyphenated term
        if d in text_normalized:
            found.append(d)
    return list(set(found))

def is_low_quality(item: dict) -> bool:
    """
    Implements strict whitelist-based ingestion:
    - Hard Rejection: BAD_PATTERNS, LEAD_CAPTURE, CONVERSATION_FILLER, MARKETING
    - Guardrail: Must have at least 1 travel keyword OR a destination mention
    """
    answer = item.get('answer', '').lower()
    text_to_check = f"{item.get('question', '').lower()} {answer}"
    
    # 1. Hard Rejection (Blacklist & Marketing Fluff)
    all_bad_patterns = (
        settings.BAD_PATTERNS + 
        settings.LEAD_CAPTURE_PATTERNS + 
        settings.CONVERSATION_FILLER_PATTERNS +
        settings.GENERIC_MARKETING_PATTERNS
    )
    for pattern in all_bad_patterns:
        if re.search(pattern, answer):
            return True
            
    # 2. Whitelist Guardrail
    has_travel_keyword = any(kw in text_to_check for kw in settings.TRAVEL_KEYWORDS)
    has_destination = any(dest in text_to_check for dest in settings.KNOWN_DESTINATIONS)
    
    if not (has_travel_keyword or has_destination):
        return True
        
    return False

def chunk_text_by_words(text: str, max_words: int = 150, overlap: int = 30) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words - overlap):
        chunk = " ".join(words[i:i + max_words])
        if len(chunk.strip()) > 50:  # Ignore tiny trailing chunks
            chunks.append(chunk)
    return chunks

def ingest_scraped_pages():
    db = get_vector_db()
    
    try:
        with open(settings.SCRAPED_PAGES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Could not find Scraped Pages at {settings.SCRAPED_PAGES_PATH}")
        return

    texts = []
    metadatas = []
    
    logger.info(f"Preparing to chunk and embed {len(data)} scraped pages...")
    
    for page in data:
        url = page.get('url', '')
        title = page.get('title', '')
        page_type = page.get('page_type', 'general')
        main_content = page.get('main_content', '')
        highlights = page.get('tour_highlights', {})
        
        # Build base metadata
        meta_base = {
            "source_url": url,
            "title": title,
            "type": page_type,
            "confidence": 1.0,
            "tags": [page_type]
        }
        
        # Extract destinations if it's a tour
        dests = highlights.get('destinations_covered', [])
        if dests:
            meta_base["destination"] = [d.lower() for d in dests]
        else:
            meta_base["destination"] = extract_destinations(main_content)
        
        # Chunk main content
        chunks = chunk_text_by_words(main_content, max_words=150, overlap=30)
        for i, chunk in enumerate(chunks):
            # Prepend context to chunk for better embedding semantic match
            chunk_text = f"Title: {title}\nContent: {chunk}"
            
            meta = meta_base.copy()
            meta["chunk_id"] = i
            meta["answer"] = chunk_text
            
            texts.append(chunk_text)
            metadatas.append(meta)
            
    logger.info(f"Generated {len(texts)} chunks from scraped pages.")
    
    BATCH_SIZE = 100
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding Scraped Chunks"):
        batch_text = texts[i:i+BATCH_SIZE]
        batch_meta = metadatas[i:i+BATCH_SIZE]
        db.add_texts(batch_text, batch_meta)

def ingest_itineraries_docs():
    """Ingests GeTS Itineraries from .docx files."""
    db = get_vector_db()
    docs_path = settings.ITINERARY_DOCS_PATH
    
    if not os.path.exists(docs_path):
        logger.error(f"Could not find Itineraries folder at {docs_path}")
        return

    all_files = [f for f in os.listdir(docs_path) if f.endswith('.docx')]
    logger.info(f"Found {len(all_files)} .docx itineraries in {docs_path}")

    texts = []
    metadatas = []

    for filename in tqdm(all_files, desc="Processing Itinerary DOCX"):
        file_path = os.path.join(docs_path, filename)
        try:
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text.strip())
            
            content = "\n".join(full_text)
            title = filename.replace("- Rewritten Itinerary", "").replace("- Rewritten itinerary", "").replace(".docx", "").strip()
            
            # Extract destination from filename or content
            dest = extract_destinations(f"{title} {content}")
            
            meta_base = {
                "source": filename,
                "title": title,
                "type": "itinerary_doc",
                "confidence": 1.0,
                "destination": dest,
                "tags": ["itinerary", "internal_doc"]
            }

            chunks = chunk_text_by_words(content, max_words=150, overlap=30)
            for i, chunk in enumerate(chunks):
                chunk_text = f"Itinerary: {title}\nContent: {chunk}"
                meta = meta_base.copy()
                meta["chunk_id"] = i
                meta["answer"] = chunk_text
                texts.append(chunk_text)
                metadatas.append(meta)

        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")

    logger.info(f"Generated {len(texts)} chunks from docx itineraries.")
    
    BATCH_SIZE = 50
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding Itinerary Batches"):
        batch_text = texts[i:i+BATCH_SIZE]
        batch_meta = metadatas[i:i+BATCH_SIZE]
        db.add_texts(batch_text, batch_meta)

def ingest_qa_pairs(overwrite: bool = True):
    """Reads cleaned qa_pairs.json and populates the Vector DB."""
    db = get_vector_db()
    
    try:
        with open(settings.QA_PAIRS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Could not find QA pairs at {settings.QA_PAIRS_PATH}")
        return

    # Clear index if overwrite requested
    if overwrite and hasattr(db, 'index'):
        import os
        import shutil
        if os.path.exists(settings.FAISS_INDEX_PATH):
            shutil.rmtree(settings.FAISS_INDEX_PATH)
            logger.info("Cleared existing FAISS index for rebuild.")
            # Re-initialize empty DB
            db = get_vector_db()
    elif not overwrite and db.get_count() > 0:
        logger.info(f"Vector DB already contains {db.get_count()} items. Skipping ingestion.")
        return

    texts = []
    metadatas = []
    
    print("Preparing data for embedding...")
    logger.info("Preparing data for embedding...")
    total_count = len(data)
    filtered_count = 0
    
    for item in data:
        # Quality Filter
        if is_low_quality(item):
            filtered_count += 1
            continue
            
        # Destination Tagging
        extracted_dest = extract_destinations(f"{item['question']} {item['answer']}")
        
        # Enhanced Metadata Tagging
        answer_lower = item['answer'].lower()
        auto_tags = item.get('tags', [])
        if any(k in answer_lower for k in ["price", "cost", "budget", "₹", "$"]):
            auto_tags.append("pricing")
        if any(k in answer_lower for k in ["days", "nights", "itinerary", "day 1", "day 2"]):
            auto_tags.append("itinerary")
        if any(k in answer_lower for k in ["hotel", "stay", "accommodation", "resort", "villa"]):
            auto_tags.append("accommodation")
        
        # We embed the question and the answer together to maximize semantic match
        text = f"User: {item['question']}\nAgent: {item['answer']}"
        meta = {
            "question": item['question'],
            "answer": item['answer'],
            "confidence": item['confidence'],
            "tags": list(set(auto_tags)), # Deduplicate
            "destination": extracted_dest,
            "entities": item.get('entities', {}),
            "source": item.get('source', 'intelliticks'),
            "conversation_id": item['conversation_id']
        }
        texts.append(text)
        metadatas.append(meta)
    
    kept_count = len(texts)
    stats = {
        "total_docs": total_count,
        "kept_docs": kept_count,
        "rejected_docs": filtered_count,
        "keep_rate": f"{(kept_count/total_count)*100:.2f}%" if total_count > 0 else "0%"
    }
    
    print(f"Ingestion Stats: {json.dumps(stats, indent=2)}")
    logger.info(f"Ingestion Stats: {json.dumps(stats, indent=2)}")
    
    if total_count > 0 and (kept_count / total_count) < 0.10:
        logger.warning("ALERT: Keep rate is below 10%! Whitelist might be too strict.")
        
    # Batch add to avoid overwhelming API limits
    BATCH_SIZE = 100
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding batches"):
        batch_text = texts[i:i+BATCH_SIZE]
        batch_meta = metadatas[i:i+BATCH_SIZE]
        db.add_texts(batch_text, batch_meta)

    logger.info("Ingestion to Vector DB complete.")

if __name__ == "__main__":
    # Ingest QA pairs first (overwrites existing index)
    ingest_qa_pairs(overwrite=True)
    # Then append scraped pages
    ingest_scraped_pages()
    # Finally append DOCX itineraries
    ingest_itineraries_docs()
