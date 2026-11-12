# Pramana read-only service. Synthetic data baked in for demonstration.
# For a real deployment, mount your own ledger and corpus (see DEPLOYMENT.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    PRAMANA_LEDGER=/data/ledger.jsonl PRAMANA_CORPUS=/data/corpus.json

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && useradd --system --uid 10001 pramana \
 && mkdir /data \
 && pramana build-synthetic --out /data \
 && mv /data/synthetic_ledger.jsonl /data/ledger.jsonl \
 && mv /data/synthetic_corpus.json /data/corpus.json \
 && chown -R pramana /data

USER pramana
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/healthz',timeout=2)"
CMD ["python", "-m", "pramana.server"]
