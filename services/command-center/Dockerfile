# =========================
# 1) BUILDER STAGE
# =========================
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better caching)
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --no-deps -r requirements.txt -w /wheels

# =========================
# 2) RUNTIME STAGE
# =========================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime-only tools (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create data directory for SQLite databases
RUN mkdir -p /app/data

# Copy wheels from builder, then install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy app source
COPY . /app

# Make sure Python can import your pkg
ENV PYTHONPATH=/app

# OCI labels for traceability
LABEL org.opencontainers.image.title="aetherlink-command-center" \
    org.opencontainers.image.description="Operator + autoheal control plane for AetherLink" \
    org.opencontainers.image.source="https://github.com/your-org/AetherLink" \
    org.opencontainers.image.version="v1.0.0" \
    org.opencontainers.image.licenses="Proprietary"

# Expose port
EXPOSE 8010

# Healthcheck so docker/k8s knows we're good
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s CMD \
    curl -f -H "X-User-Roles: admin" http://localhost:8010/healthz || exit 1

# Run the application on 8010 to match docker-compose and host
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
