from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import traceback
from config import settings

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.schemas import ChatRequest, ChatResponse, SourceDocument
from services.intent import extract_intent_and_entities
from services.retrieval import retrieve_context
from services.ranking import rank_results
from services.generation import generate_response, generate_response_stream

# Configure Logging Base
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Thread pool for running synchronous retrieval without blocking the event loop
executor = ThreadPoolExecutor(max_workers=4)

app = FastAPI(
    title="GeTS Travel Hybrid RAG API",
    description="Production-grade conversational RAG API filtering Structured & IntelliTicks data through a strict LLM boundary.",
    version="1.1.0"
)

# --- Startup Health Heartbeat ---
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 [STARTUP] GeTS Chatbot Backend is Initializing...")
    
    # 1. Check Database and Embedding Configuration
    try:
        from config import settings
        from utils.vector_db import get_vector_db
        db = get_vector_db()
        count = db.get_count()
        logger.info(f"✅ [DATABASE] Supabase Connected! Current Vectors: {count}")
        
        # Validate Dimension Consistency
        configured_dim = 384 if settings.EMBEDDING_PROVIDER == "fastembed" else 3072
        logger.info(f"✅ [DATABASE] Configured Embedding Dimension: {configured_dim} ({settings.EMBEDDING_PROVIDER})")
        
    except Exception as e:
        logger.error(f"❌ [DATABASE] Connection or Configuration Failed: {e}")

    # 2. Check AI Providers (Real token test)
    try:
        from services.generation import check_ai_status
        ai_results = await check_ai_status()
        for provider, status in ai_results.items():
            logger.info(f"{status} [AI-{provider.upper()}] Status Check")
    except Exception as e:
        logger.error(f"❌ [AI-STATUS] Could not perform provider check: {e}")

@app.get("/health")
async def health_check():
    from services.generation import check_ai_status
    from utils.vector_db import get_vector_db
    
    ai_status = await check_ai_status()
    db_count = "unknown"
    try:
        db = get_vector_db()
        db_count = db.get_count()
    except Exception as e:
        logger.warning(f"Health check could not retrieve vector count: {e}")
        pass

    return {
        "status": "ok",
        "database": {"vectors": db_count},
        "ai_providers": ai_status
    }

# Manual CORS handling - Ultra Permissive for Production Hardening
@app.middleware("http")
async def add_cors_headers(request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
    
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

LOG_FILE = "rag_log.jsonl"

def log_observability(query: str, intent: dict, docs: list, answer: str):
    """Write telemetry to local JSONL and echo to stdout for Railway logging."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "intent": intent,
        "retrieved_docs": [doc.get("question", "UNKNOWN") for doc in docs],
        "final_answer": answer
    }
    
    # 1. Echo to standard logger so it appears in Railway Dashboard
    logger.info(f"📊 [OBSERVABILITY] Query: \"{query}\" | Intent: {intent.get('intent', 'none')} | Docs Found: {len(docs)}")
    
    # 2. Write to local file (ephemeral)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write observability log: {e}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Execute Hybrid RAG execution loop combining retrieval parameters and explicit confidence tracking.
    """
    try:
        start_time = datetime.utcnow()
        logger.info(f"[REQUEST] Query received: \"{request.query}\"")

        # ----------------------------------------------------------------
        # Step 1: Sequential Intent and Retrieval
        # Intent must be extracted FIRST to allow retrieve_context to boost 
        # results based on destination/entities.
        # ----------------------------------------------------------------
        conversation_history = getattr(request, "conversation_history", []) or []
        intent_info = await extract_intent_and_entities(request.query, history=conversation_history)
        
        logger.info(f"[INTENT] Extracted: destination={intent_info.destination}, intent={intent_info.intent}, rewritten='{intent_info.rewritten_query}'")

        # ----------------------------------------------------------------
        # Step 2: Conditional Retrieval & Re-ranking
        # ----------------------------------------------------------------
        ranked_docs = []
        if intent_info.rewritten_query.strip():
            # Run retrieval with the extracted intent
            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(
                executor,
                retrieve_context,
                request.query,
                intent_info
            )
            logger.info(f"[RETRIEVAL] Found {len(raw_results)} chunks")

            if not raw_results:
                logger.warning(f"[RETRIEVAL] Zero results found for: \"{request.query}\"")
                ranked_docs = []
            else:
                ranked_docs = rank_results(raw_results, top_k=10)
                
                if ranked_docs:
                    top_score = round(ranked_docs[0].get('final_score', 0.0), 4)
                    logger.info(f"[RETRIEVAL] Reranked top score: {top_score}")

                    # Hard confidence threshold
                    CONFIDENCE_THRESHOLD = 0.10
                    if top_score < CONFIDENCE_THRESHOLD:
                        logger.warning(f"[RETRIEVAL] Score {top_score} below threshold {CONFIDENCE_THRESHOLD} — deferring to LLM")
                        ranked_docs = []  # Clear docs to force LLM graceful pivot
                else:
                    logger.warning("[RETRIEVAL] No docs passed reranking filters — deferring to LLM")
                    ranked_docs = []
        else:
            logger.info("ℹ️ [RETRIEVAL] Skipped Vector DB search for generic conversational intent.")

        # ----------------------------------------------------------------
        # Step 3: Generate response — pass conversation_history from request
        # ----------------------------------------------------------------
        gen_start = datetime.utcnow()

        answer = await generate_response(
            query=request.query,
            ranked_docs=ranked_docs,
            conversation_history=conversation_history
        )

        gen_duration = (datetime.utcnow() - gen_start).total_seconds()
        total_duration = (datetime.utcnow() - start_time).total_seconds()

        logger.info(f"[GENERATION] Response generated in {gen_duration:.2f}s")
        logger.info(f"[PIPELINE] Total request completed in {total_duration:.2f}s")

        # ----------------------------------------------------------------
        # Step 5: Build response
        # ----------------------------------------------------------------
        sources = [
            SourceDocument(
                content=doc.get('answer', ''),
                metadata={
                    "source": doc.get('source', ''),
                    "confidence": doc.get('confidence', ''),
                    "tags": doc.get('tags', []),
                    "original_q": doc.get('question', '')
                },
                score=round(doc.get('final_score', 0.0), 4)
            ) for doc in ranked_docs
        ]

        overall_conf = "low"
        if sources:
            top_src_conf = sources[0].metadata.get("confidence")
            if top_src_conf == "high" or sources[0].metadata.get("source") == "database":
                overall_conf = "high"
            elif top_src_conf == "medium":
                overall_conf = "medium"

        log_observability(request.query, intent_info.dict(), ranked_docs, answer)

        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence=overall_conf,
            metadata=intent_info
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"[ERROR] Chat extraction failed for query \"{request.query}\": {str(e)}")
        logger.error("🔥 FULL ERROR TRACE:")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error: Sorry, I'm having trouble connecting. Please try again."
        )


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Streaming version of the chat endpoint.
    Runs the same parallel intent + retrieval pipeline, then streams
    Gemini tokens to the frontend via Server-Sent Events (SSE).
    """
    async def event_stream():
        try:
            start_time = datetime.utcnow()
            logger.info(f"🌊 [STREAM] Query received: \"{request.query}\"")

            # --- Step 1: Intent Extraction ---
            conversation_history = getattr(request, "conversation_history", []) or []
            intent_info = await extract_intent_and_entities(request.query, history=conversation_history)
            
            # --- Step 2: Conditional Retrieval ---
            ranked_docs = []
            if intent_info.rewritten_query.strip():
                loop = asyncio.get_event_loop()
                raw_results = await loop.run_in_executor(
                    executor,
                    retrieve_context,
                    request.query,
                    intent_info
                )
                
                logger.info(f"🔎 [STREAM] Found {len(raw_results)} raw results from search")
                
                if not raw_results:
                    logger.warning(f"⚠️ [STREAM] Zero results found for: \"{request.query}\"")
                    ranked_docs = []
                else:
                    ranked_docs = rank_results(raw_results, top_k=10)
                    if not ranked_docs:
                        logger.warning("⚠️ [STREAM] No docs passed reranking filters")
                        ranked_docs = []
                    else:
                        top_score = ranked_docs[0].get('final_score', 0.0)
                        logger.info(f"📊 [STREAM] Top Match Score: {top_score:.4f} (Threshold: 0.10)")
                        if top_score < 0.10:
                            logger.warning(f"⚠️ [STREAM] Score {top_score} below threshold — deferring to LLM")
                            ranked_docs = []
            else:
                logger.info("ℹ️ [STREAM] Skipped Vector DB search for generic conversational intent.")

            # --- Step 3: Stream Generation ---
            gen_start = datetime.utcnow()
            full_answer = ""

            async for token in generate_response_stream(
                query=request.query,
                ranked_docs=ranked_docs,
                conversation_history=conversation_history
            ):
                full_answer += token
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"

            gen_duration = (datetime.utcnow() - gen_start).total_seconds()
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"✅ [STREAM] Completed in {total_duration:.2f}s | Words: {len(full_answer.split())}")
            log_observability(request.query, intent_info.dict(), ranked_docs, full_answer)

        except Exception as e:
            logger.error(f"🔥 [STREAM-ERROR] Failed for query \"{request.query}\": {str(e)}")
            logger.error(traceback.format_exc())
            yield "data: [ERROR] I'm having trouble right now. Please try again.\n\n"
        
        finally:
            # Ensure safe closure in all paths
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)