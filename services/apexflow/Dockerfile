FROM python:3.11-slim
WORKDIR /app

# Install curl for healthchecks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Copy Alembic configuration and migrations
COPY alembic ./alembic
COPY alembic.ini .

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PORT=8080
EXPOSE 8080

# Use entrypoint script for auto-migration
ENTRYPOINT ["/entrypoint.sh"]
