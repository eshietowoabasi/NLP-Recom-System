# Single-container demo for a Hugging Face Docker Space (docs/HOSTING.md).
# Runs PostgreSQL, Redis, the API, the Celery worker and scheduler, and Nginx under
# supervisord, as the non-root user (uid 1000) that Spaces require. Data lives inside
# the container, so it is lost whenever the Space restarts.
# Build context: the repository root.

FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    NUMBA_CACHE_DIR=/tmp/numba-cache

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential postgresql redis-server nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Bake the SBERT model into the image (BAKE_SBERT=0 only for offline test builds).
ARG BAKE_SBERT=1
ARG SBERT_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV SBERT_MODEL=${SBERT_MODEL}
RUN if [ "$BAKE_SBERT" = "1" ]; then \
      python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['SBERT_MODEL'])"; \
    fi

COPY backend/ /app/
COPY --from=frontend /app/dist /srv/www
COPY deploy/huggingface/nginx.conf /etc/nginx/nginx.conf
COPY deploy/huggingface/supervisord.conf /etc/supervisor/nlprs.conf
COPY deploy/huggingface/start.sh /usr/local/bin/start-nlprs

RUN useradd --create-home --uid 1000 user \
    && mkdir -p /data /opt/hf-cache \
    && chown -R user /app /data /opt/hf-cache /srv/www \
    && chmod +x /usr/local/bin/start-nlprs
USER user
WORKDIR /app

ENV APP_CONFIG=production \
    FLASK_APP=wsgi.py \
    BEHIND_PROXY=1 \
    EMBEDDING_BACKEND=sbert \
    HF_HUB_OFFLINE=1 \
    PGDATA=/data/postgres \
    DATABASE_URL=postgresql+psycopg2://user@/nlprs?host=/tmp \
    REDIS_URL=redis://127.0.0.1:6379/0 \
    UPLOAD_FOLDER=/data/raw \
    REPORT_FOLDER=/data/reports

EXPOSE 7860
CMD ["start-nlprs"]
