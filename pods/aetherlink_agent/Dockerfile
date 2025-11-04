FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 agent && \
    mkdir -p /app && \
    chown -R agent:agent /app

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./

# Switch to non-root user
USER agent

# Expose port
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
