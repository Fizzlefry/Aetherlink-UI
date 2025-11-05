FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY ./main.py /app/main.py
COPY ./rbac.py /app/rbac.py
COPY ./audit.py /app/audit.py
COPY ./event_store.py /app/event_store.py
COPY ./alert_store.py /app/alert_store.py
COPY ./alert_evaluator.py /app/alert_evaluator.py
COPY ./routers /app/routers

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
