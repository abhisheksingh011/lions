# Dockerfile for the Hugging Face Space (flat layout).
# The Space folder contains: this Dockerfile, the *.py files, requirements.txt,
# and rules_index.npz — all in one directory.

FROM python:3.11-slim

# HF Spaces run the container on port 7860.
ENV PORT=7860 \
    HF_HOME=/app/.cache \
    TRANSFORMERS_CACHE=/app/.cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model at build time so cold starts are faster.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Make caches writable for the non-root Space user.
RUN mkdir -p /app/.cache && chmod -R 777 /app/.cache

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
