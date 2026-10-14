# Build context must be the project root.
#
# docker-compose sets:  build: { context: ., dockerfile: etn_onboarding/Dockerfile }
# Manual build example: docker build -f etn_onboarding/Dockerfile -t etn-onboarding .

FROM python:3.12

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENSSL_CONF=/dev/null

WORKDIR /app

# ── Dependencies (separate layer for cache efficiency) ───────────────────────
COPY etn_onboarding/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────────────────
COPY ./etn_onboarding/ ./etn_onboarding

RUN chmod +x ./etn_onboarding/entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

ENTRYPOINT ["./etn_onboarding/entrypoint.sh"]
