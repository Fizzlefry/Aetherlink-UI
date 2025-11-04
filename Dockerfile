# ---- deps layer (cached) ----
FROM python:3.11-slim AS deps
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl wget && rm -rf /var/lib/apt/lists/*
COPY pods/customer_ops/requirements.txt /app/pods/customer_ops/requirements.txt
RUN python -m pip install -U pip && pip install -r /app/pods/customer_ops/requirements.txt

# ---- runtime ----
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . /app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "pods.customer_ops.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
