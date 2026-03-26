"""
GeTS Holidays — Standalone Ingestion Pipeline
=============================================
Reads:   data/raw/scraped_pages.json  (480 website pages)
         output/qa_pairs.json         (IntelliTicks conversations)
Writes:  rag_api/faiss_index/         (replaces existing index)
         data/processed/ingest_summary.json

Run from the PROJECT ROOT:
    python ingestion/scraper/ingest_scraped.py
"""

import sys
import os
import json
import pickle
import logging
import shutil
import re
from datetime import datetime
from typing import List, Dict, Any

import numpy as np
import faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths — all relative to project root (where script is launched from)
# ---------------------------------------------------------------------------
PROJECT_ROOT       = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
SCRAPED_PAGES_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "scraped_pages.json")
QA_PAIRS_PATH      = os.path.join(PROJECT_ROOT, "output", "qa_pairs.json")
FAISS_INDEX_DIR    = os.path.join(PROJECT_ROOT, "rag_api", "faiss_index")
FAISS_BACKUP_DIR   = os.path.join(PROJECT_ROOT, "rag_api", "faiss_index_backup")
SUMMARY_OUT_PATH   = os.path.join(PROJECT_ROOT, "data", "processed", "ingest_summary.json")

EMBEDDING_MODEL    = "all-MiniLM-L6-v2"
EMBEDDING_DIM      = 384
BATCH_SIZE         = 64
MIN_CHUNK_WORDS    = 50
CHUNK_SIZE_WORDS   = 300
CHUNK_OVERLAP_WORDS = 50

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tag auto-detection
# ---------------------------------------------------------------------------
TAG_KEYWORDS: Dict[str, List[str]] = {
    "destination": [
        "kerala", "rajasthan", "goa", "delhi", "agra", "jaipur", "kashmir",
        "himachal", "ladakh", "varanasi", "amritsar", "udaipur", "rishikesh",
        "andaman", "golden triangle", "south india", "north india", "nepal",
        "bhutan", "sri lanka", "mumbai", "bangalore", "mysore", "coorg",
        "manali", "shimla", "darjeeling", "sikkim", "ranthambore", "corbett",
    ],
    "pricing": [
        "price", "cost", "budget", "package price", "per person", "starting from",
        "₹", "$", "usd", "inr", "rs.", "fee", "charge", "rate",
    ],
    "itinerary": [
        "day 1", "day 2", "day 3", "itinerary", "schedule", "night", "nights",
        "days", "morning", "afternoon", "evening", "visit", "depart", "arrive",
    ],
    "accommodation": [
        "hotel", "resort", "stay", "lodge", "hostel", "villa", "camp",
        "houseboat", "property", "room", "suite", "deluxe", "5 star", "3 star",
    ],
    "transport": [
        "flight", "train", "transfer", "cab", "taxi", "car", "bus",
        "airport pickup", "pickup", "drop", "transit",
    ],
}


def detect_tags(text: str) -> List[str]:
    text_lower = text.lower()
    return [tag for tag, kws in TAG_KEYWORDS.items() if any(kw in text_lower for kw in kws)]


# ---------------------------------------------------------------------------
# Text chunking helpers
# ---------------------------------------------------------------------------

def chunk_by_words(text: str, chunk_size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> List[str]:
    """Split *text* into sliding windows of *chunk_size* words with *overlap*."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def is_long_enough(text: str) -> bool:
    return len(text.split()) >= MIN_CHUNK_WORDS


# ---------------------------------------------------------------------------
# STEP 1 — Generate website chunks
# ---------------------------------------------------------------------------

def build_website_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    docs = []

    for page in pages:
        url       = page.get("url", "")
        title     = page.get("title", "").strip()
        meta      = page.get("meta_description", "").strip()
        page_type = page.get("page_type", "general")
        headings  = page.get("headings", [])
        main_content = page.get("main_content", "").strip()
        highlights   = page.get("tour_highlights", {})

        confidence = "high" if page_type == "tour_package" else "medium"

        def make_doc(chunk_text: str) -> Dict[str, Any]:
            return {
                "source":    "website",
                "page_type": page_type,
                "url":       url,
                "source_url": url,
                "confidence": confidence,
                "tags":       detect_tags(chunk_text),
                "question":   title,
                "answer":     chunk_text,
            }

        # --- Chunk 1: title + meta description ---
        title_meta = f"{title}. {meta}" if meta else title
        if is_long_enough(title_meta):
            docs.append(make_doc(title_meta))

        # --- Chunks 2+: main content with sliding window ---
        if main_content:
            for chunk in chunk_by_words(main_content):
                if is_long_enough(chunk):
                    docs.append(make_doc(chunk))

        # --- Chunk: headings (if meaningful) ---
        if len(headings) > 2:
            heading_text = f"{title}: " + " | ".join(headings)
            if is_long_enough(heading_text):
                docs.append(make_doc(heading_text))

        # --- Chunk: tour highlights (tour_package pages only) ---
        if page_type == "tour_package" and highlights:
            duration   = highlights.get("duration") or ""
            dests      = highlights.get("destinations_covered") or []
            inclusions = highlights.get("inclusions") or []

            if duration or dests:
                parts = [title]
                if duration:
                    parts.append(f"Duration: {duration}")
                if dests:
                    parts.append("Destinations: " + ", ".join(dests))
                if inclusions:
                    parts.append("Inclusions: " + ", ".join(inclusions[:10]))
                highlight_text = ". ".join(parts)
                if is_long_enough(highlight_text):
                    docs.append(make_doc(highlight_text))

    return docs


# ---------------------------------------------------------------------------
# STEP 2 — Load IntelliTicks QA pairs
# ---------------------------------------------------------------------------

def load_intelliticks(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Keep only entries with a meaningful answer
    valid = []
    for entry in data:
        answer = (entry.get("answer") or "").strip()
        if is_long_enough(answer):
            valid.append(entry)
    return valid


# ---------------------------------------------------------------------------
# STEP 3 — Deduplicate by 90% character overlap
# ---------------------------------------------------------------------------

CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def char_overlap_ratio(a: str, b: str) -> float:
    """Simple character-level overlap: |intersection| / min(|a|, |b|)."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def deduplicate(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by first-200-char fingerprint. O(n), no over-filtering."""
    seen_hashes = set()
    unique_docs = []

    for doc in documents:
        answer = doc.get("answer", "").strip()

        # Skip empty answers
        if not answer:
            continue

        # Create a fingerprint from first 200 characters of answer
        # This catches true duplicates without over-filtering
        fingerprint = answer[:200].lower().strip()

        if fingerprint not in seen_hashes:
            seen_hashes.add(fingerprint)
            unique_docs.append(doc)

    return unique_docs


# ---------------------------------------------------------------------------
# STEP 4 — Embed and build FAISS index
# ---------------------------------------------------------------------------

def embed_and_build(docs: List[Dict[str, Any]], encoder: SentenceTransformer) -> faiss.IndexFlatIP:
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    texts = [doc["answer"] for doc in docs]

    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
    all_embeddings = []

    for batch_num in range(total_batches):
        batch = texts[batch_num * BATCH_SIZE : (batch_num + 1) * BATCH_SIZE]
        logger.info(f"[INGEST] Embedding batch {batch_num + 1}/{total_batches}")
        embeddings = encoder.encode(
            batch,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True,   # cosine via IP
        )
        all_embeddings.append(embeddings)

    all_np = np.vstack(all_embeddings).astype("float32")
    # Re-normalize (sentence_transformers may already do it, but be safe)
    faiss.normalize_L2(all_np)
    index.add(all_np)
    return index


# ---------------------------------------------------------------------------
# STEP 5 — Save index + metadata
# ---------------------------------------------------------------------------

def save_index(index: faiss.IndexFlatIP, metadatas: List[Dict[str, Any]]):
    # Safety backup of existing index
    if os.path.exists(FAISS_INDEX_DIR):
        if os.path.exists(FAISS_BACKUP_DIR):
            shutil.rmtree(FAISS_BACKUP_DIR)
        shutil.copytree(FAISS_INDEX_DIR, FAISS_BACKUP_DIR)
        logger.info(f"[INGEST] Backup saved to {FAISS_BACKUP_DIR}")

    os.makedirs(FAISS_INDEX_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(FAISS_INDEX_DIR, "index.faiss"))
    with open(os.path.join(FAISS_INDEX_DIR, "metadata.pkl"), "wb") as f:
        pickle.dump(metadatas, f)
    logger.info(f"[INGEST] New index saved to {FAISS_INDEX_DIR}")


def save_summary(website_chunks: int, intelliticks_docs: int, total: int, pages_by_type: Dict[str, int]):
    os.makedirs(os.path.dirname(SUMMARY_OUT_PATH), exist_ok=True)
    summary = {
        "total_documents":   total,
        "website_chunks":    website_chunks,
        "intelliticks_docs": intelliticks_docs,
        "pages_by_type":     pages_by_type,
        "embedding_model":   EMBEDDING_MODEL,
        "built_at":          datetime.now().isoformat(),
    }
    with open(SUMMARY_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"[INGEST] Summary written to {SUMMARY_OUT_PATH}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    start = datetime.now()
    logger.info("[INGEST] Starting ingestion pipeline")

    # ── Step 1: Load scraped pages ─────────────────────────────────────────
    with open(SCRAPED_PAGES_PATH, "r", encoding="utf-8") as f:
        scraped_pages = json.load(f)
    logger.info(f"[INGEST] Loaded {len(scraped_pages)} scraped pages")

    website_docs = build_website_chunks(scraped_pages)
    logger.info(f"[INGEST] Generated {len(website_docs)} chunks from website data")

    pages_by_type: Dict[str, int] = {}
    for p in scraped_pages:
        pt = p.get("page_type", "unknown")
        pages_by_type[pt] = pages_by_type.get(pt, 0) + 1

    # ── Step 2: Load IntelliTicks ──────────────────────────────────────────
    intelliticks_docs = load_intelliticks(QA_PAIRS_PATH)
    logger.info(f"[INGEST] Loaded {len(intelliticks_docs)} IntelliTicks documents")

    # ── Step 3: Combine + Deduplicate ─────────────────────────────────────
    all_docs = website_docs + intelliticks_docs
    logger.info(
        f"[INGEST] Website chunks: {len(website_docs)} | IntelliTicks docs: {len(intelliticks_docs)}"
    )

    deduped = deduplicate(all_docs)

    logger.info(f"[INGEST] After deduplication: {len(deduped)} total documents")
    logger.info(f"[INGEST] Total to embed: {len(deduped)}")

    # ── Step 4: Embed ──────────────────────────────────────────────────────
    logger.info(f"[INGEST] Loading embedding model: {EMBEDDING_MODEL}")
    encoder = SentenceTransformer(EMBEDDING_MODEL)

    index = embed_and_build(deduped, encoder)
    logger.info(f"[INGEST] FAISS index built with {index.ntotal} vectors")

    # ── Step 5: Save ───────────────────────────────────────────────────────
    save_index(index, deduped)
    save_summary(len(website_docs), len(intelliticks_docs), len(deduped), pages_by_type)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"[INGEST] DONE in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
