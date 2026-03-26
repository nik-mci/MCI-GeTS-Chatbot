from fastapi import FastAPI, HTTPException
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
    version="1.0.0"
)

# Add CORS Middleware to allow Next.js frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = "rag_log.jsonl"

def log_observability(query: str, intent: dict, docs: list, answer: str):
    """Write telemetry to local JSONL for debugging bad retrievals."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "intent": intent,
        "retrieved_docs": [doc.get("question", "UNKNOWN") for doc in docs],
        "final_answer": answer
    }
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
        if not settings.GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY environment variable")

        start_time = datetime.utcnow()
        logger.info(f"[REQUEST] Query received: \"{request.query}\"")

        # ----------------------------------------------------------------
        # Step 1: Run Intent Extraction + Retrieval IN PARALLEL
        # Intent uses the raw query — so does retrieval.
        # They are independent and can run simultaneously.
        # retrieve_context is synchronous (FAISS), so we offload it to a
        # thread pool to avoid blocking the async event loop.
        # ----------------------------------------------------------------
        loop = asyncio.get_event_loop()

        parallel_start = datetime.utcnow()

        conversation_history = getattr(request, "conversation_history", []) or []
        intent_task = extract_intent_and_entities(request.query, history=conversation_history)
        retrieval_task = loop.run_in_executor(
            executor,
            retrieve_context,
            request.query,
            None  # intent_info not available yet — retrieval uses raw query
        )

        # Run both concurrently — total time = max(intent_time, retrieval_time)
        intent_info, raw_results = await asyncio.gather(intent_task, retrieval_task)

        parallel_duration = (datetime.utcnow() - parallel_start).total_seconds()
        logger.info(f"[INTENT] Extracted: destination={intent_info.destination}, budget={intent_info.budget}, duration={intent_info.duration}")
        logger.info(f"[RETRIEVAL] Found {len(raw_results)} chunks")
        logger.info(f"[PIPELINE] Intent + Retrieval completed in parallel in {parallel_duration:.2f}s")

        # ----------------------------------------------------------------
        # Step 2: Empty fallback — if retrieval returned nothing
        # ----------------------------------------------------------------
        if not raw_results:
            fallback = "I couldn't find exact relevant travel information based on available data. Please refine your query or contact GeTS support for a custom itinerary!"
            log_observability(request.query, intent_info.dict(), [], fallback)
            return ChatResponse(
                answer=fallback,
                sources=[],
                confidence="low",
                metadata=intent_info
            )

        # ----------------------------------------------------------------
        # Step 3: Re-rank results (synchronous, fast — no LLM involved)
        # ----------------------------------------------------------------
        ranked_docs = rank_results(raw_results, top_k=3)

        if ranked_docs:
            top_score = round(ranked_docs[0].get('final_score', 0.0), 4)
            logger.info(f"[RETRIEVAL] Reranked top score: {top_score}")

            # Hard confidence threshold — if best match is too weak,
            # skip LLM generation entirely and return honest fallback
            CONFIDENCE_THRESHOLD = 0.15
            if top_score < CONFIDENCE_THRESHOLD:
                logger.warning(f"[RETRIEVAL] Score {top_score} below threshold {CONFIDENCE_THRESHOLD} — returning fallback")
                fallback = "I don't have specific information on that in my current knowledge base. GeTS Holidays specializes in incredible India tours — I'd love to help you explore destinations like Kerala, Rajasthan, the Golden Triangle, or Kashmir. Or I can connect you with our travel experts directly!"
                log_observability(request.query, intent_info.dict(), [], fallback)
                return ChatResponse(
                    answer=fallback,
                    sources=[],
                    confidence="low",
                    metadata=intent_info
                )
        else:
            fallback = "I couldn't find exact relevant travel information based on available data. Please refine your query or contact GeTS support!"
            log_observability(request.query, intent_info.dict(), [], fallback)
            return ChatResponse(
                answer=fallback,
                sources=[],
                confidence="low",
                metadata=intent_info
            )

        # ----------------------------------------------------------------
        # Step 4: Generate response — pass conversation_history from request
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
    No extra API cost — same Gemini call, just token-by-token delivery.
    """
    async def event_stream():
        try:
            if not settings.GEMINI_API_KEY:
                yield "data: [ERROR] Missing GEMINI_API_KEY\n\n"
                return

            start_time = datetime.utcnow()
            logger.info(f"[REQUEST] Stream query received: \"{request.query}\"")

            # --- Parallel intent + retrieval (same as /chat) ---
            loop = asyncio.get_event_loop()
            parallel_start = datetime.utcnow()

            conversation_history = getattr(request, "conversation_history", []) or []
            intent_task = extract_intent_and_entities(request.query, history=conversation_history)
            retrieval_task = loop.run_in_executor(
                executor,
                retrieve_context,
                request.query,
                None
            )

            intent_info, raw_results = await asyncio.gather(intent_task, retrieval_task)

            parallel_duration = (datetime.utcnow() - parallel_start).total_seconds()
            logger.info(f"[INTENT] Extracted: destination={intent_info.destination}, budget={intent_info.budget}, duration={intent_info.duration}")
            logger.info(f"[RETRIEVAL] Found {len(raw_results)} chunks")
            logger.info(f"[PIPELINE] Intent + Retrieval completed in parallel in {parallel_duration:.2f}s")

            # --- Fallback if no results ---
            if not raw_results:
                fallback = "I couldn't find exact relevant travel information. Please refine your query or contact GeTS support for a custom itinerary!"
                log_observability(request.query, intent_info.dict(), [], fallback)
                yield f"data: {fallback}\n\n"
                yield "data: [DONE]\n\n"
                return

            # --- Re-rank ---
            ranked_docs = rank_results(raw_results, top_k=3)
            if not ranked_docs:
                fallback = "I couldn't find exact relevant travel information. Please refine your query or contact GeTS support!"
                log_observability(request.query, intent_info.dict(), [], fallback)
                yield f"data: {fallback}\n\n"
                yield "data: [DONE]\n\n"
                return

            if ranked_docs:
                top_score = round(ranked_docs[0].get('final_score', 0.0), 4)
                logger.info(f"[RETRIEVAL] Reranked top score: {top_score}")

            # --- Stream generation token by token ---
            gen_start = datetime.utcnow()
            full_answer = ""

            logger.info(f"[GENERATION] Starting stream | Query: '{request.query}' | Docs: {len(ranked_docs)}")

            async for token in generate_response_stream(
                query=request.query,
                ranked_docs=ranked_docs,
                conversation_history=conversation_history
            ):
                full_answer += token
                # Encode token as SSE — escape newlines so they don't break the protocol
                safe_token = token.replace("\n", "\\n")
                yield f"data: {safe_token}\n\n"

            gen_duration = (datetime.utcnow() - gen_start).total_seconds()
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[GENERATION] Stream completed in {gen_duration:.2f}s | Words: {len(full_answer.split())}")
            logger.info(f"[PIPELINE] Total stream request completed in {total_duration:.2f}s")

            log_observability(request.query, intent_info.dict(), ranked_docs, full_answer)

            # Signal to frontend that stream is done
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[ERROR] Stream failed for query \"{request.query}\": {str(e)}")
            logger.error(traceback.format_exc())
            yield "data: [ERROR] I'm having trouble right now. Please try again.\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Prevents Nginx from buffering the stream
        }
    )