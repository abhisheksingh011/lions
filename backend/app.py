"""
FastAPI backend for Cricket Rules Search.

Endpoints:
  GET  /health   -> liveness check (also used by the frontend to pre-warm)
  POST /search   -> { "question": "..." } -> { "answer", "sources" }

Protections (the Space is public, so guard the free Groq quota):
  - per-IP rate limiting
  - in-memory response cache for repeated questions
  - CORS limited to the configured frontend origin(s)
"""
from __future__ import annotations

import os
import time
from collections import OrderedDict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from retrieval import Retriever
import llm

# --- config (override via Space env vars / secrets) ---------------------------
TOP_K = int(os.environ.get("TOP_K", "5"))
# Comma-separated list of allowed origins; "*" allows any (fine for a public demo).
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))   # requests/min/IP
CACHE_SIZE = int(os.environ.get("CACHE_SIZE", "256"))

app = FastAPI(title="Cricket Rules Search", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

retriever = Retriever()
_cache: "OrderedDict[str, dict]" = OrderedDict()
_hits: dict[str, deque] = {}   # ip -> timestamps (sliding window)


class SearchRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


@app.on_event("startup")
def _startup() -> None:
    retriever.load()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ready": retriever.ready, "chunks": len(retriever.chunks)}


def _rate_limited(ip: str) -> bool:
    now = time.time()
    dq = _hits.setdefault(ip, deque())
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


@app.post("/search")
def search(req: SearchRequest, request: Request) -> JSONResponse:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        return JSONResponse(
            status_code=429,
            content={"answer": "Too many requests — please wait a minute and retry.",
                     "sources": [], "error": "rate_limit"},
        )

    if not retriever.ready:
        return JSONResponse(
            status_code=503,
            content={"answer": "The service is still starting up. Please retry in a moment.",
                     "sources": [], "error": "warming_up"},
        )

    key = " ".join(req.question.lower().split())
    if key in _cache:
        _cache.move_to_end(key)
        return JSONResponse(content={**_cache[key], "cached": True})

    chunks = retriever.search(req.question, k=TOP_K)
    result = llm.answer(req.question, chunks)

    if result.get("error") is None:        # only cache good answers
        _cache[key] = result
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)

    return JSONResponse(content=result)


@app.get("/")
def root() -> dict:
    return {"service": "Cricket Rules Search API", "endpoints": ["/health", "/search"]}
