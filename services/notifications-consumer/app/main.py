import json
import logging
import os
import threading
import time
from typing import Any

import requests
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from kafka import KafkaConsumer
from pydantic import BaseModel

"""
AetherLink Notifications Consumer
- Subscribes to ApexFlow domain events
- Applies simple rules
- Emits webhooks (Slack-style) to a configured endpoint
"""

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
NOTIFY_WEBHOOK = os.getenv("NOTIFY_WEBHOOK", "")  # leave blank to disable
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "aetherlink-notifications")
TENANT_FILTER = os.getenv("TENANT_FILTER", "")  # e.g. "acme" to only notify for that tenant
RULES_PATH = os.getenv("RULES_PATH", "/app/rules.yaml")

TOPICS = [
    "apexflow.leads.created",
    "apexflow.leads.status_changed",
    "apexflow.leads.assigned",
    "apexflow.leads.note_added",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("notifications-consumer")

app = FastAPI(title="AetherLink Notifications Consumer", version="0.1.0")


# ------------------------------------------------------------------------------
# Models
# ------------------------------------------------------------------------------
class Notification(BaseModel):
    event_type: str
    tenant_id: str
    title: str
    message: str
    raw: dict[str, Any]


# ------------------------------------------------------------------------------
# Rules Engine
# ------------------------------------------------------------------------------
def load_rules() -> dict[str, Any]:
    if not os.path.exists(RULES_PATH):
        log.warning("rules file not found at %s, using default allow", RULES_PATH)
        return {
            "rules": [],
            "default": {
                "notify": True,
                "template": "[{tenant_id}] {event_type} on lead #{lead_id}",
            },
        }

    with open(RULES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        data.setdefault("rules", [])
        data.setdefault("default", {"notify": True})
        return data


# Global rules state
RULESET: dict[str, Any] = load_rules()


def get_ruleset() -> dict[str, Any]:
    return RULESET


def reload_ruleset() -> dict[str, Any]:
    global RULESET
    RULESET = load_rules()
    log.info("Rules reloaded: %d rules", len(RULESET.get("rules", [])))
    return RULESET


def match_rule(event: dict[str, Any]) -> dict[str, Any]:
    """
    Return the first matching rule, or the default.
    """
    for rule in RULESET.get("rules", []):
        cond = rule.get("match", {})
        matched = True
        for key, value in cond.items():
            # event could have nested keys, keep it flat for now
            if event.get(key) != value:
                matched = False
                break
        if matched:
            return rule
    return RULESET.get("default", {"notify": True})


def render_template(tpl: str, event: dict[str, Any]) -> str:
    # very simple {field} replace
    def repl(key: str) -> str:
        return str(event.get(key, ""))

    out = tpl
    for part in [
        "tenant_id",
        "event_type",
        "lead_id",
        "id",
        "name",
        "email",
        "actor",
        "old_status",
        "new_status",
    ]:
        out = out.replace("{" + part + "}", repl(part))
    return out


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def passes_tenant_filter(event: dict[str, Any]) -> bool:
    tenant_id = event.get("tenant_id")
    if TENANT_FILTER and tenant_id != TENANT_FILTER:
        return False
    return True


def build_notification(event: dict[str, Any]) -> Notification | None:
    if not passes_tenant_filter(event):
        return None

    rule = match_rule(event)
    rule_name = rule.get("name", "default")

    if not rule.get("notify", True):
        log.info("Notification suppressed by rule=%s", rule_name)
        return None

    log.info("Notification matched rule=%s", rule_name)

    tpl = rule.get("template") or "[{tenant_id}] {event_type} on lead #{lead_id}"
    message = render_template(tpl, event)

    tenant_id = event.get("tenant_id", "unknown")
    et = event.get("event_type") or "unknown"
    lead_id = event.get("id") or event.get("lead_id") or "?"

    return Notification(
        event_type=et,
        tenant_id=tenant_id,
        title=f"{et} ({tenant_id})",
        message=message,
        raw=event,
    )


def send_webhook(notification: Notification) -> None:
    if not NOTIFY_WEBHOOK:
        log.info("Webhook disabled, skipping send: %s", notification.title)
        return
    try:
        resp = requests.post(
            NOTIFY_WEBHOOK,
            json={
                "text": f"{notification.title}\n{notification.message}",
                "tenant_id": notification.tenant_id,
                "event_type": notification.event_type,
                "raw": notification.raw,
            },
            timeout=5,
        )
        log.info("Webhook sent (%s): %s", resp.status_code, notification.title)
    except Exception as e:
        log.exception("Failed to send webhook: %s", e)


def start_consumer() -> None:
    """
    Run Kafka consumer in a background thread.
    """
    while True:
        try:
            consumer = KafkaConsumer(
                *TOPICS,
                bootstrap_servers=KAFKA_BROKERS.split(","),
                group_id=GROUP_ID,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                enable_auto_commit=True,
                auto_offset_reset="earliest",
            )
            log.info("Notifications consumer started. Topics: %s", TOPICS)

            for msg in consumer:
                event = msg.value
                notif = build_notification(event)
                if notif:
                    log.info("Notification created: %s", notif.title)
                    send_webhook(notif)
        except Exception as e:
            log.exception("Kafka consumer error, retrying in 5s: %s", e)
            time.sleep(5)


# ------------------------------------------------------------------------------
# FastAPI endpoints
# ------------------------------------------------------------------------------
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "aetherlink-notifications-consumer"}


@app.get("/rules", tags=["operations"])
def get_rules():
    """
    Return the currently loaded rules (what the service is actually using).
    """
    return get_ruleset()


@app.post("/rules/reload", tags=["operations"])
def post_rules_reload():
    """
    Reload rules from disk. Use when you edited /app/rules.yaml on the host.
    """
    new_rules = reload_ruleset()
    return {"status": "reloaded", "rules": len(new_rules.get("rules", []))}


@app.post("/test-notification", tags=["testing"])
def test_notification(payload: dict[str, Any]):
    notif = build_notification(payload)
    if notif:
        send_webhook(notif)
        return notif
    else:
        return JSONResponse(
            status_code=200,
            content={"message": "Notification suppressed by rules", "event": payload},
        )


# ------------------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------------------
def _boot():
    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()


_boot()
