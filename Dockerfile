FROM python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENSSL_CONF=/dev/null

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib -type d -name "tests"       -exec rm -rf {} + 2>/dev/null; true \
    && find /usr/local/lib -type d -name "test"        -exec rm -rf {} + 2>/dev/null; true \
    && find /usr/local/lib -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true

COPY *.py ./
COPY *.json ./
COPY templates/ templates/
COPY entrypoint.sh ./

# config.json is NOT baked in (excluded via .dockerignore).
# In K8s: mount via ConfigMap (cribl-config) at /app/config.json
# Locally: -v ./config.json:/app/config.json:ro
# In prod: set APP_CONFIG_JSON env var (from CyberArk Conjur) — entrypoint writes it to /app/config.json

RUN chmod +x /app/entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/cribl/health')" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
