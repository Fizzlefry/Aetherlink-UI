FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OS deps for psycopg2 & healthcheck curl
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only the pod's requirements
COPY pods/customer_ops/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the whole repo (so imports like pods.customer_ops.* work)
COPY . /app

# Defaults; override via env/compose in prod
ENV PORT=8000 UVICORN_WORKERS=2

EXPOSE 8000

# Uvicorn entrypoint
CMD ["python", "-m", "uvicorn", "pods.customer_ops.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
