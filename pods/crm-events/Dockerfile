FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 9010

# Use 'auto' to enable HTTP/2 when h2 is installed
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9010", "--http", "auto"]
