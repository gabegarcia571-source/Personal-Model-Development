# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r /app/requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder /wheels /wheels
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements.txt && \
    rm -rf /wheels

COPY . /app

RUN mkdir -p /app/data/input /app/data/output && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,os,sys;port=os.getenv('PORT','8501');url=f'http://127.0.0.1:{port}/_stcore/health';\
resp=urllib.request.urlopen(url,timeout=3);sys.exit(0 if resp.status==200 else 1)"

CMD ["sh", "-c", "streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=${PORT}"]
