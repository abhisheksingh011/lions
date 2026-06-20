"""
Assemble a clean, flat folder to deploy to the Hugging Face Space.

    python scripts/build_space.py

Produces  space_build/  containing exactly what the Space needs:
    Dockerfile, requirements.txt, app.py, retrieval.py, indexing.py, llm.py,
    rules_index.npz, README.md

Upload the CONTENTS of space_build/ to your Space (drag-drop in the HF web UI,
or push with git). No PDFs, no raw docs — just the running backend + index.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
INDEX = ROOT / "data" / "index" / "rules_index.npz"
OUT = ROOT / "space_build"

SPACE_README = """\
---
title: Cricket Rules Search
emoji: 🏏
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Cricket Rules Search — Backend API

FastAPI backend for natural-language cricket rules search (BCMCL / ICC / MCC).
See `app.py` for endpoints: `GET /health`, `POST /search`.

Set `GROQ_API_KEY` as a Space **Secret** (Settings -> Variables and secrets).
"""


def main() -> None:
    if not INDEX.exists():
        raise SystemExit("rules_index.npz not found. Run  python ingest.py  first.")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for name in ("Dockerfile", "requirements.txt", "app.py",
                 "retrieval.py", "indexing.py", "llm.py"):
        shutil.copy2(BACKEND / name, OUT / name)
    shutil.copy2(INDEX, OUT / "rules_index.npz")
    (OUT / "README.md").write_text(SPACE_README, encoding="utf-8")

    files = sorted(p.name for p in OUT.iterdir())
    print(f"Built {OUT} with: {', '.join(files)}")
    print("Next: upload the contents of space_build/ to your HF Space.")


if __name__ == "__main__":
    main()
