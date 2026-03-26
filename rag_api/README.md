# GeTS Travel Chatbot - Hybrid RAG System

This is the production-grade FastAPI backend enabling the GeTS Holidays AI Chatbot core systems. It explicitly tackles real-world noisy data constraints by combining pre-filtering metadata layers with vector-search retrieval methods, followed by prioritized re-ranking mechanics assuring future SQL datastores overrule IntelliTicks conversational history logs natively.

## Project Structure Overview
```text
rag_api/
├── main.py                 # FastAPI application routes
├── config.py               # Env Configuration settings
├── requirements.txt        # PIP modules
├── models/
│   └── schemas.py          # Strict Pydantic models for HTTP requests, inputs, targets
└── services/
    ├── ingestion.py        # Isolated Vector Database building
    ├── intent.py           # Extracts Entity Tags + NLP logic to JSON schema
    ├── retrieval.py        # Primary querying & Metadata verification pre-filters
    ├── ranking.py          # Enforces explicit scoring overrides scaling sources manually
    └── generation.py       # OpenAI interface dictating conversational AI output rules
```

## Non-Functional Traits Executed
1. Memory / Compute Efficient Pipeline
2. Highly extendable API structure built around `services/` dependencies
3. Database Agnostic: Core `VectorDB` model interface class enabling trivial transition away from `FAISS` to your finalized `Supabase/pgvector` instance.

## Boot Sequence Instructions

### 1) Initialize Virtual Environment
Make sure you are utilizing an active Python virtualenv running >3.9+ environments natively.
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Required Env Configurations
Store keys locally in `.env` or system configurations:
```bash
export OPENAI_API_KEY="sk-PROJ-....." 
```

### 3) Ingest Vector Embeddings (One-Time Execution)
Populate the FAISS abstraction model utilizing the pre-processed records exported in earlier steps into your directory tree root outputs vector store arrays.
```bash
python services/ingestion.py
```

### 4) Expose Server via Uvicorn Fast HTTP Daemon Layer
```bash
uvicorn main:app --reload
# Default configuration deploys HTTP accessible endpoints exposed across 0.0.0.0:8000
```

## API Structure Test Execution Sequence Output Schema
Execute arbitrary test logic across local environments ensuring API connectivity structures natively filter expected results correctly.

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
          "query": "Can you arrange a 5 day package to Rajasthan?"
         }'
```

Returns natively explainable output architectures mapped matching exact API instructions structured identically:
```json
{
  "answer": "Yes, I'd be happy to arrange exploring Rajasthan packages with you. For a 5 nights...",
  "sources": [
    {
      "content": "Looking to explore Rajasthan deeply, how many nights package are you searching? We have several standard golden triangle and royal routes spanning 4 to 8 nights specifically focused around touring major destinations within.",
      "metadata": {
        "source": "intelliticks",
        "confidence": "high",
        "tags": ["destination", "booking"],
        "original_q": "magical rajasthan tour"
      },
      "score": 0.8123
    }
  ],
  "confidence": "high",
  "metadata": {
    "destination": ["Rajasthan"],
    "budget": null,
    "duration": "5 day",
    "travel_date": null,
    "intent": "itinerary"
  }
}
```
