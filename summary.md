# Cricket Rules Search — Project Spec

A natural-language search app for cricket rules. A user types a question in plain English ("if the batter is out of the crease and the keeper breaks the stumps, is it run out or stumped?") and gets a clear answer grounded in three rule sources, in priority order:

1. **BCMCL** — British Columbia Mainland Cricket League (local league rules) — *highest priority*
2. **ICC** — International Cricket Council playing conditions
3. **MCC** — Marylebone Cricket Club Laws of Cricket — *fallback*

This is a free, non-commercial hobby project. The entire stack must stay on free tiers.

---

## Tech Stack (all free)

| Layer | Choice | Role |
|-------|--------|------|
| Frontend | **GitHub Pages** | Static HTML/CSS/JS. Search box + results. |
| Backend | **Hugging Face Spaces** (Python, FastAPI or Gradio) | Hides API keys, runs retrieval, calls the LLM. |
| Embeddings | **`sentence-transformers`** (e.g. `all-MiniLM-L6-v2`), runs locally inside the Space | Turns text into vectors. No external API. |
| Retrieval | **In-memory cosine similarity** over pre-computed vectors (numpy or FAISS) | No vector database to host. |
| LLM | **Groq** free tier (e.g. `llama-3.3-70b-versatile`) | Generates the final answer from retrieved rules. |

**Why no vector database:** the rule set is tiny (three documents). We embed all rules once at build time, commit the vectors as a static file, and load them into memory on startup. Cosine similarity with numpy is enough. This avoids Hugging Face's ephemeral-storage problem (a hosted DB would get wiped on restart) and removes a moving part.

---

## Architecture & Request Flow

```
[GitHub Pages UI]
      |  (1) POST { question }
      v
[Hugging Face Space — backend]
      |  (2) embed question  -> sentence-transformers (in-process)
      |  (3) cosine similarity vs pre-computed rule vectors (in memory)
      |  (4) take top-K chunks (each tagged with source: BCMCL/ICC/MCC)
      |  (5) build prompt: question + retrieved chunks + priority instructions
      |  (6) call Groq API  ---------------------> [Groq]
      |  (7) receive natural-language answer <----
      v
[GitHub Pages UI]  (8) render answer + cite which source/rule it came from
```

---

## Build-Time Step (do this once, re-run when rules change)

A script `ingest.py` that:

1. Reads the three raw rule files from `data/raw/` (`bcmcl.md`, `icc.md`, `mcc.md`).
2. **Chunks** each document into small logical units — one rule / sub-clause per chunk. *Do not embed whole documents as a single vector; long text dilutes meaning. Chunking is the biggest lever on retrieval quality.*
3. Tags each chunk with metadata: `{ source: "BCMCL"|"ICC"|"MCC", rule_id, text }`.
4. Embeds every chunk with `all-MiniLM-L6-v2`.
5. Saves vectors + metadata to `data/index/rules_index.npz` (or `.pkl`), committed to the repo.

The backend loads this file on startup — no embedding of the corpus at runtime.

---

## Backend Endpoints

`POST /search`
- Body: `{ "question": "..." }`
- Steps: embed question → cosine sim → top-K (start with K=5) → prompt Groq → return `{ "answer": "...", "sources": [{source, rule_id}] }`
- Must handle Groq `429` (rate limit) gracefully and return a friendly message, not a crash.

`GET /health` — simple liveness check (also handy to ping and wake the Space).

---

## Source Priority Logic

Don't try to force priority into the vector math. Instead:

1. Retrieve top-K across **all three** sources together (so cross-referencing works).
2. Pass the source label of each chunk into the LLM prompt.
3. Instruct the model in the system prompt:
   > "Answer using the retrieved rules. If a BCMCL rule covers the question, base the answer on BCMCL. Otherwise use ICC. If neither applies, use MCC. Always state which source and rule number the answer comes from. If none of the retrieved rules answer the question, say so — do not invent a rule."

This keeps priority simple, allows cross-references, and prevents hallucinated rules.

---

## Known Constraints / Gotchas (build for these)

- **HF free Spaces sleep when idle.** First request after idle has a cold start (~30s+). The UI must show a clear loading state. Optionally ping `/health` to pre-warm.
- **Groq free tier:** generous on requests (~30 RPM / ~1,000 RPD) but has token-per-minute caps. Keep retrieved context tight — send top 3–5 chunks, not 20.
- **API keys never touch the frontend.** The Groq key lives only as a secret in the Hugging Face Space settings. GitHub Pages calls *your backend*, never Groq directly.
- **CORS:** backend must allow requests from your GitHub Pages domain.
- **No hallucinated rules:** the prompt must force "if not found, say not found."
- *(Optional alternative to consider: a serverless function — Cloudflare Workers / Vercel — avoids the cold-start sleep and is purpose-built for "hide key + proxy call." Trade-off: embeddings/retrieval are easier to run in the Python Space. Sticking with HF Spaces is fine for v1.)*

---

## Suggested Repo Structure

```
cricket-rules-search/
├── frontend/                 # deploy to GitHub Pages
│   ├── index.html
│   ├── style.css
│   └── app.js                # fetch() to HF Space /search
├── backend/                  # deploy to Hugging Face Space
│   ├── app.py                # FastAPI/Gradio: /search, /health
│   ├── retrieval.py          # load index, embed query, cosine sim, top-K
│   ├── llm.py                # Groq call + prompt building + error handling
│   └── requirements.txt      # fastapi, sentence-transformers, numpy, groq, ...
├── ingest.py                 # build-time: chunk + embed + save index
├── data/
│   ├── raw/                  # bcmcl.md, icc.md, mcc.md
│   └── index/                # rules_index.npz (committed)
└── README.md
```

---

## Build Order (suggested for Claude Code)

1. Set up repo structure + `requirements.txt`.
2. Add placeholder rule files in `data/raw/` (real content can be pasted later).
3. Write `ingest.py` — chunking + embedding + save index. Run it, verify the index file.
4. Write `retrieval.py` — load index, embed a query, return top-K. Test standalone.
5. Write `llm.py` — Groq call with the priority prompt + 429 handling.
6. Wire up `app.py` — `/search` and `/health`, with CORS for the Pages domain.
7. Build the frontend — search box, loading state, results with source citation.
8. Deploy backend to HF Space (set Groq key as a secret), deploy frontend to GitHub Pages, connect them.
9. Test cold start, rate limits, and a "rule not found" case.

---

## v1 Definition of Done

- A user on the GitHub Pages site can type a natural-language cricket question.
- They get a correct, readable answer that names the source (BCMCL/ICC/MCC) and rule.
- Questions with no matching rule return an honest "not found," never a made-up rule.
- Whole stack runs on free tiers with keys hidden.
