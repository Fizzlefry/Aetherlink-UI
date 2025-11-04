FROM python:3.11-slim

WORKDIR /app

# Copy application files
COPY ./main.py /app/main.py
COPY ./rbac.py /app/rbac.py

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
