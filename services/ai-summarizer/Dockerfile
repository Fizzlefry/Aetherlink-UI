# services/ai-summarizer/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

ENV APEXFLOW_BASE=http://apexflow:8080
ENV CLAUDE_ENDPOINT=https://api.anthropic.com/v1/messages
ENV CLAUDE_MODEL=claude-3-sonnet-20240229

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9108"]
