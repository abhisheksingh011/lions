"""
Build-time step. Run this once locally (and again whenever the rules change):

    python ingest.py

It reads every markdown file in data/raw/, chunks + embeds them, and writes
the index to data/index/rules_index.npz. The backend loads that file on
startup, so no embedding of the corpus happens at request time.

Source is taken from the filename prefix before "__":
    bcmcl__playing-rules.md  -> source = BCMCL
    mcc__laws-of-cricket.md  -> source = MCC
    icc__playing-conditions.md -> source = ICC   (add this file when available)
"""
from pathlib import Path

from backend.indexing import build_index, save_index, load_index

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
INDEX_PATH = ROOT / "data" / "index" / "rules_index.npz"


def main() -> None:
    print(f"Reading rule files from {RAW_DIR}")
    vectors, chunks = build_index(RAW_DIR)
    save_index(INDEX_PATH, vectors, chunks)

    size_kb = INDEX_PATH.stat().st_size / 1024
    by_source: dict[str, int] = {}
    for c in chunks:
        by_source[c.source] = by_source.get(c.source, 0) + 1

    print("\n" + "=" * 50)
    print(f"Saved {len(chunks)} chunks -> {INDEX_PATH} ({size_kb:.0f} KB)")
    print(f"Vector shape: {vectors.shape}")
    print("Chunks per source:", ", ".join(f"{k}={v}" for k, v in sorted(by_source.items())))

    # Sanity check: reload and show a sample.
    _, reloaded = load_index(INDEX_PATH)
    assert len(reloaded) == len(chunks), "reload mismatch!"
    sample = reloaded[len(reloaded) // 2]
    print("\nSample chunk:")
    print(f"  [{sample.source}] {sample.section} (rule {sample.rule_id or '-'})")
    print(f"  {sample.text[:200]}{'...' if len(sample.text) > 200 else ''}")
    print("=" * 50)
    print("OK. Commit data/index/rules_index.npz to the repo.")


if __name__ == "__main__":
    main()
