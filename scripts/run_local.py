"""
Run the backend locally for testing, before deploying to the Space.

    .venv/Scripts/python scripts/run_local.py

Then:
  - open http://127.0.0.1:8000/health  in a browser, and
  - open frontend/index.html  (it auto-points to localhost when served locally).

Set your Groq key first so /search can answer:
  PowerShell:  $env:GROQ_API_KEY = "gsk_..."
  Git Bash:    export GROQ_API_KEY="gsk_..."
"""
import os
import sys
from pathlib import Path

# Use the OS trust store so requests through an SSL-inspecting proxy work
# (needed for the Groq API call on some networks).
try:
    import truststore
    truststore.inject_into_ssl()
except ModuleNotFoundError:
    pass

# Model is already cached locally from ingest.py — load it offline, no network.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
