# 🏏 Cricket Rules Search

A natural-language search app for cricket rules. Ask a question in plain English
and get a clear answer grounded in three rule sources, in priority order:

1. **BCMCL** — British Columbia Mainland Cricket League (local rules) — *highest priority*
2. **ICC** — International Cricket Council playing conditions *(add later)*
3. **MCC** — Marylebone Cricket Club Laws of Cricket — *fallback*

Built entirely on **free tiers**. Pattern: **RAG** (Retrieval-Augmented Generation).
See [architecture.html](architecture.html) for a full visual walkthrough.

---

## How it works (3 layers)

```
[Browser · GitHub Pages]  --POST /search-->  [Hugging Face Space · FastAPI]  --->  [Groq LLM]
   search box + answer                        embed → cosine search → prompt        writes answer
```

- **Frontend** (`frontend/`) — static HTML/CSS/JS, deploys to GitHub Pages.
- **Backend** (`backend/`) — FastAPI on a Hugging Face Space: retrieval + Groq call.
- **Index** (`data/index/rules_index.npz`) — pre-computed embeddings of every rule
  chunk, committed to the repo so nothing is embedded at request time.

---

## Project layout

```
cricket/
├── frontend/            # → GitHub Pages
│   ├── index.html
│   ├── style.css
│   ├── config.js        # set BACKEND_URL here
│   └── app.js
├── backend/             # → Hugging Face Space (via space_build/)
│   ├── app.py           # FastAPI: /search, /health  (+ CORS, rate-limit, cache)
│   ├── retrieval.py     # load index, embed query, cosine top-K, rule-id hybrid
│   ├── llm.py           # Groq call + priority prompt + 429 handling
│   ├── indexing.py      # shared: clean → chunk → tag → embed
│   ├── requirements.txt
│   └── Dockerfile
├── ingest.py            # build-time: builds data/index/rules_index.npz
├── scripts/build_space.py
├── data/
│   ├── raw/             # source rule markdown (source = filename prefix before "__")
│   └── index/           # rules_index.npz  (committed)
└── README.md
```

---

## Rebuild the index (run when rules change)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install numpy==1.26.4 sentence-transformers==3.3.1
.venv/Scripts/python ingest.py
```

> On a network with an SSL-inspecting proxy, first `pip install truststore`, then run
> `python -c "import truststore; truststore.inject_into_ssl(); import runpy; runpy.run_path('ingest.py', run_name='__main__')"`.

To add **ICC** rules later: drop `icc__playing-conditions.md` into `data/raw/` and re-run.

---

## Deploy

### 1. Backend → Hugging Face Space (`voice4varun/cricket`, Docker)

```bash
python scripts/build_space.py     # assembles space_build/ (flat, no PDFs)
```

Then either:
- **Web UI:** open the Space → *Files* → upload everything inside `space_build/`, **or**
- **Git:** push the contents of `space_build/` to the Space's git repo.

In the Space → **Settings → Variables and secrets**, add a secret:

| Name | Value |
|------|-------|
| `GROQ_API_KEY` | *(your Groq key)* |

Optional env vars: `GROQ_MODEL` (default `llama-3.3-70b-versatile`),
`ALLOWED_ORIGINS` (set to your GitHub Pages URL once known),
`RATE_LIMIT_PER_MIN` (default 10), `TOP_K` (default 5).

The Space builds the Docker image and starts on port 7860. Check
`https://voice4varun-cricket.hf.space/health`.

### 2. Frontend → GitHub Pages

1. Confirm `frontend/config.js` points to your Space URL.
2. In the GitHub repo → **Settings → Pages**, serve from the `frontend/` folder
   (or move `frontend/` contents to a `docs/` folder / `gh-pages` branch).
3. Once live, set the Space's `ALLOWED_ORIGINS` to your Pages URL for tighter CORS.

---

## Notes / constraints

- **Cold start:** free HF Spaces sleep when idle; the first request can take ~30s.
  The frontend pings `/health` on load to pre-warm and shows a loading state.
- **Groq free tier:** ~30 req/min. The backend rate-limits per IP and caches
  repeated questions to protect the quota; `429`s return a friendly message.
- **Keys never touch the frontend** — `GROQ_API_KEY` lives only as a Space secret.
- **Copyright:** MCC Laws are © Marylebone Cricket Club. This is a non-commercial
  hobby tool; the rule text is embedded in the committed index.
