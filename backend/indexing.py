"""
Shared indexing logic: clean -> chunk -> tag -> embed -> save/load.

Used by both:
  - ingest.py  (build-time, run locally, commits the index)
  - retrieval.py (startup fallback: build the index in-process if it's missing)

Chunking is the biggest lever on answer quality, so the rules here are
deliberately simple and predictable:

  * A line that starts with a number ("1.", "12.3", "Law 24") begins a new chunk.
  * That number becomes the chunk's rule_id.
  * The nearest preceding heading is kept as `section` for context + citations.
  * Wrapped/continuation lines are appended to the current chunk.
  * Over-long chunks are split; tiny noise chunks are dropped.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"
MAX_CHARS = 1600          # split chunks longer than this
OVERLAP_CHARS = 160       # overlap when splitting long chunks
MIN_CHARS = 25            # drop shorter noise chunks (unless they carry a rule_id)

# A numbered rule item:  "1. ...", "12.3 ...", "4) ..."
_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]\s+(.+)$")
# An MCC law:  "Law 24 ...", "Law 41.3 ..."
_LAW_RE = re.compile(r"^Law\s+(\d+(?:\.\d+)*)\b[.:]?\s*(.*)$", re.IGNORECASE)

# Lines that are page furniture / boilerplate we don't want as content.
_DROP_RE = re.compile(
    r"^(www\.\S+|©.*|world copyright.*|copies may be obtained.*|lord'?s.*|"
    r"london nw8.*|marylebone cricket club\s*$|the\s*$|official\s*$)",
    re.IGNORECASE,
)


@dataclass
class Chunk:
    id: int
    source: str          # "BCMCL" | "ICC" | "MCC"
    doc: str             # source filename (for traceability)
    section: str         # nearest heading, for context + citation
    rule_id: str         # e.g. "12.3" or "" if none
    text: str            # the rule text itself (what we show the user)


def _clean_lines(raw: str) -> list[str]:
    """Normalise whitespace and strip page furniture, keeping line structure."""
    out: list[str] = []
    for line in raw.splitlines():
        s = " ".join(line.split())  # collapse internal whitespace
        if not s:
            out.append("")
            continue
        if re.fullmatch(r"\d{1,4}", s):     # lone page number
            continue
        if _DROP_RE.match(s):
            continue
        out.append(s)
    return out


def _looks_like_heading(line: str) -> bool:
    low = line.lower()
    if any(k in low for k in ("local rules", "regulations", "playing conditions",
                              "match conditions", "preamble", "preface", "appendix")):
        return True
    # Short ALL-CAPS title line
    letters = re.sub(r"[^A-Za-z]", "", line)
    if letters and line.upper() == line and len(line.split()) <= 12 and len(line) > 3:
        return True
    return False


def _split_long(text: str) -> list[str]:
    """Split an over-long chunk on sentence-ish boundaries with light overlap."""
    if len(text) <= MAX_CHARS:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        if end < len(text):  # try to break at a sentence/space boundary
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("; "), window.rfind(" "))
            if cut > MAX_CHARS // 2:
                end = start + cut + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return [p for p in parts if p]


def chunk_document(raw: str, source: str, doc: str) -> list[dict]:
    """Turn one document's raw text into a list of chunk dicts (no ids yet)."""
    lines = _clean_lines(raw)
    section = ""
    cur_id = ""           # current rule_id
    cur_lines: list[str] = []
    chunks: list[dict] = []

    def flush():
        if not cur_lines:
            return
        text = " ".join(cur_lines).strip()
        if len(text) < MIN_CHARS and not cur_id:
            return
        for piece in _split_long(text):
            chunks.append({"source": source, "doc": doc,
                           "section": section, "rule_id": cur_id, "text": piece})

    for line in lines:
        if line == "":
            continue
        m = _NUM_RE.match(line) or _LAW_RE.match(line)
        if m:
            flush()
            cur_id, rest = m.group(1), (m.group(2) or "").strip()
            cur_lines = [rest] if rest else []
        elif _looks_like_heading(line):
            flush()
            cur_id, cur_lines = "", []
            section = line
        else:
            cur_lines.append(line)
    flush()
    return chunks


# ---------------------------------------------------------------------------
# Embedding model (lazy singleton — loading it is the slow part)
# ---------------------------------------------------------------------------
_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Return L2-normalised float32 embeddings (so dot product == cosine sim)."""
    vecs = get_model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True,
        show_progress_bar=len(texts) > 64, batch_size=64,
    )
    return vecs.astype(np.float32)


# ---------------------------------------------------------------------------
# Build / save / load
# ---------------------------------------------------------------------------
def build_index(raw_dir: Path) -> tuple[np.ndarray, list[Chunk]]:
    """Read every *.md in raw_dir, chunk, embed. Source = filename prefix before '__'."""
    raw_dir = Path(raw_dir)
    files = sorted(raw_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No .md rule files found in {raw_dir}")

    raw_chunks: list[dict] = []
    for f in files:
        source = f.name.split("__", 1)[0].upper() if "__" in f.name else "BCMCL"
        text = f.read_text(encoding="utf-8", errors="ignore")
        doc_chunks = chunk_document(text, source, f.name)
        raw_chunks.extend(doc_chunks)
        print(f"  {f.name:45s} -> {len(doc_chunks):4d} chunks  [{source}]")

    chunks = [Chunk(id=i, **c) for i, c in enumerate(raw_chunks)]
    # Embed section + text together (a little context helps retrieval).
    embed_texts = [f"{c.section}\n{c.text}".strip() for c in chunks]
    print(f"Embedding {len(embed_texts)} chunks with {MODEL_NAME} ...")
    vectors = embed(embed_texts)
    return vectors, chunks


def save_index(path: Path, vectors: np.ndarray, chunks: list[Chunk]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = json.dumps([asdict(c) for c in chunks], ensure_ascii=False)
    np.savez_compressed(path, embeddings=vectors, meta=np.array(meta))


def load_index(path: Path) -> tuple[np.ndarray, list[Chunk]]:
    data = np.load(Path(path), allow_pickle=False)
    vectors = data["embeddings"].astype(np.float32)
    meta = json.loads(str(data["meta"]))
    chunks = [Chunk(**m) for m in meta]
    return vectors, chunks
