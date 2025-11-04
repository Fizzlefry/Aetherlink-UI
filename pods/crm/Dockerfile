FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 crm && \
    mkdir -p /app && \
    chown -R crm:crm /app

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Switch to non-root user
USER crm

# Expose port
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn crm.main:app --host 0.0.0.0 --port 8080"]
