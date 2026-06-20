"""
LLM layer: build the prompt from retrieved rules, call Groq, return an answer.

Key behaviours required by the spec:
  - Enforce source priority BCMCL > ICC > MCC via the system prompt.
  - Force the model to cite source + rule number, and to say "not found"
    rather than invent a rule.
  - Handle Groq rate limits (429) and other errors gracefully — never crash.
"""
from __future__ import annotations

import os

from groq import Groq, RateLimitError, APIError

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = (
    "You are a cricket rules assistant for the BCMCL (British Columbia Mainland "
    "Cricket League). Answer ONLY using the retrieved rules provided below.\n\n"
    "Source priority: if a BCMCL rule covers the question, base the answer on "
    "BCMCL. Otherwise use ICC. If neither applies, use MCC (the Laws of Cricket). "
    "BCMCL local rules always override ICC and MCC where they conflict.\n\n"
    "Rules you must follow:\n"
    "1. Always state which source (BCMCL/ICC/MCC) and rule number the answer "
    "comes from.\n"
    "2. If the retrieved rules do not answer the question, say so honestly — "
    "do NOT invent or guess a rule.\n"
    "3. Be clear and concise. Quote the relevant rule wording when helpful.\n"
)

# Friendly messages instead of raw stack traces.
_RATE_LIMIT_MSG = (
    "The service is briefly rate-limited (free tier). Please wait a few seconds "
    "and try again."
)
_GENERIC_ERR_MSG = (
    "Sorry — something went wrong reaching the language model. Please try again."
)

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=key)
    return _client


def _build_user_prompt(question: str, chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        rid = f" rule {c['rule_id']}" if c.get("rule_id") else ""
        sec = f" — {c['section']}" if c.get("section") else ""
        blocks.append(f"[{c['source']}{rid}{sec}]\n{c['text']}")
    context = "\n\n".join(blocks) if blocks else "(no rules retrieved)"
    return (
        f"Retrieved rules:\n\n{context}\n\n"
        f"-----\nQuestion: {question}\n\n"
        "Answer using only the retrieved rules above, following the priority and "
        "citation requirements."
    )


def answer(question: str, chunks: list[dict]) -> dict:
    """Return {answer, sources, error}. `error` is None on success."""
    sources = [
        {"source": c["source"], "rule_id": c.get("rule_id", ""),
         "section": c.get("section", "")}
        for c in chunks
    ]
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(question, chunks)},
            ],
            temperature=0.2,
            max_tokens=700,
        )
        return {"answer": resp.choices[0].message.content.strip(),
                "sources": sources, "error": None}
    except RateLimitError:
        return {"answer": _RATE_LIMIT_MSG, "sources": [], "error": "rate_limit"}
    except (APIError, Exception) as exc:  # noqa: BLE001 - never crash the endpoint
        print(f"[llm] error: {exc!r}")
        return {"answer": _GENERIC_ERR_MSG, "sources": [], "error": "llm_error"}
