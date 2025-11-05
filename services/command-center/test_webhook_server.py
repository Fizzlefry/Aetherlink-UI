"""
Simple webhook receiver for testing Phase VII M1 notifications.
Receives POST requests and logs the payload.
"""

from fastapi import FastAPI, Request
import uvicorn
from datetime import datetime

app = FastAPI(title="Webhook Test Server")

received_webhooks = []


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receive and log webhook payload"""
    body = await request.json()
    timestamp = datetime.now().isoformat()
    
    webhook_data = {
        "received_at": timestamp,
        "payload": body,
    }
    
    received_webhooks.append(webhook_data)
    
    print(f"\n{'='*60}")
    print(f"🔔 WEBHOOK RECEIVED at {timestamp}")
    print(f"{'='*60}")
    print(f"Payload: {body}")
    print(f"{'='*60}\n")
    
    return {"status": "ok", "received_at": timestamp}


@app.get("/webhooks")
async def list_webhooks():
    """List all received webhooks"""
    return {
        "status": "ok",
        "count": len(received_webhooks),
        "webhooks": received_webhooks,
    }


if __name__ == "__main__":
    print("🚀 Starting webhook test server on http://localhost:9999")
    print("📥 Endpoint: http://localhost:9999/webhook")
    uvicorn.run(app, host="0.0.0.0", port=9999)
