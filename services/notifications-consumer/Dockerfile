FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY rules.yaml ./rules.yaml

ENV PYTHONUNBUFFERED=1

EXPOSE 9107

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9107"]
