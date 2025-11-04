FROM python:3.11-slim

WORKDIR /app
COPY ./main.py /app/main.py
COPY ./rbac.py /app/rbac.py

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
