"""
Retrieval: load the pre-computed index (or build it on first use if missing),
embed the user's question, and return the top-K most relevant rule chunks.

Includes a small hybrid step: if the question mentions a specific rule number
(e.g. "Law 41.3" or "rule 12.3"), we make sure that exact rule is included
alongside the semantic matches — embeddings alone are weak at exact-ID lookup.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

from indexing import build_index, save_index, load_index, embed, Chunk

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"


def _resolve_index_path() -> Path:
    """Find the index across both layouts: repo (data/index/) and flat (Space)."""
    candidates = [
        os.environ.get("INDEX_PATH"),
        ROOT / "data" / "index" / "rules_index.npz",   # repo / local layout
        HERE / "rules_index.npz",                       # flat layout (HF Space)
        Path.cwd() / "rules_index.npz",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    # Default write location if we have to build it.
    return ROOT / "data" / "index" / "rules_index.npz"


INDEX_PATH = _resolve_index_path()

# Captures "rule 12.3", "law 41", "regulation 7.2"
_RULE_REF_RE = re.compile(r"\b(?:law|rule|regulation|reg|clause)\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE)


class Retriever:
    def __init__(self) -> None:
        self.vectors: np.ndarray | None = None
        self.chunks: list[Chunk] = []

    def load(self) -> None:
        """Load the committed index; if absent, build it from data/raw/ once."""
        if INDEX_PATH.exists():
            print(f"Loading index from {INDEX_PATH}")
            self.vectors, self.chunks = load_index(INDEX_PATH)
        else:
            print("Index not found — building from data/raw/ (first run only).")
            self.vectors, self.chunks = build_index(RAW_DIR)
            try:
                save_index(INDEX_PATH, self.vectors, self.chunks)
            except OSError:
                pass  # ephemeral FS (e.g. HF Space) — fine, we have it in memory
        print(f"Retriever ready: {len(self.chunks)} chunks.")

    @property
    def ready(self) -> bool:
        return self.vectors is not None and len(self.chunks) > 0

    def search(self, question: str, k: int = 5) -> list[dict]:
        if not self.ready:
            raise RuntimeError("Retriever not loaded")

        q_vec = embed([question])[0]                 # normalised
        scores = self.vectors @ q_vec                # cosine similarity
        top_idx = np.argsort(-scores)[:k].tolist()

        # Hybrid: pull in any exact rule-number matches the user named.
        for ref in _RULE_REF_RE.findall(question):
            for i, c in enumerate(self.chunks):
                if c.rule_id == ref and i not in top_idx:
                    top_idx.append(i)

        results = []
        for i in top_idx:
            c = self.chunks[i]
            results.append({
                "source": c.source,
                "rule_id": c.rule_id,
                "section": c.section,
                "doc": c.doc,
                "text": c.text,
                "score": round(float(scores[i]), 4),
            })
        return results
