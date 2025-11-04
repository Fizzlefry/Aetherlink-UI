# AetherLink Notifications Consumer

Event-driven notification service that listens to ApexFlow domain events and sends webhooks.

## What It Does

- **Subscribes** to Kafka topics (leads.created, leads.status_changed, leads.assigned, leads.note_added)
- **Filters** events by tenant (optional)
- **Formats** human-readable notifications
- **Sends** webhooks to configured endpoint (Slack, Teams, custom)

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BROKERS` | `kafka:9092` | Kafka bootstrap servers |
| `KAFKA_GROUP_ID` | `aetherlink-notifications` | Consumer group ID |
| `TENANT_FILTER` | `""` | Only notify for specific tenant (e.g., `acme`) |
| `NOTIFY_WEBHOOK` | `""` | Webhook URL (leave empty to disable) |

## Quick Start

### Build and Run

```bash
cd infra/core
docker compose -f docker-compose.core.yml up -d --build notifications-consumer
```

### Check Health

```bash
curl http://localhost:9107/health
```

### Test Notification

```powershell
curl -X POST http://localhost:9107/test-notification `
  -H "Content-Type: application/json" `
  -d '{
    "event_type": "lead.created",
    "tenant_id": "acme",
    "id": 42,
    "name": "Test Lead",
    "email": "test@example.com",
    "actor": "sarah@acme.com"
  }'
```

### View Active Rules

```powershell
Invoke-RestMethod -Uri http://localhost:9107/rules | ConvertTo-Json -Depth 10
```

### Hot-Reload Rules

Edit `rules.yaml` and reload without restart:

```powershell
# 1. Edit the rules file
code services/notifications-consumer/rules.yaml

# 2. Reload (no rebuild/restart needed!)
Invoke-RestMethod -Method POST -Uri http://localhost:9107/rules/reload

# 3. Verify new rules loaded
Invoke-RestMethod -Uri http://localhost:9107/rules
```

## Webhook Format

Sends JSON payloads to configured endpoint:

```json
{
  "text": "[acme] New lead created\nLead #42 (Test Lead) was created by sarah@acme.com",
  "tenant_id": "acme",
  "event_type": "lead.created",
  "raw": { /* full event payload */ }
}
```

## Notification Rules

Rules are defined in `rules.yaml` and loaded at startup. **No code changes needed** to modify notification behavior!

**Hot-Reload:** Edit `rules.yaml` and call `POST /rules/reload` - no rebuild required!

### Rule Structure

```yaml
rules:
  - name: "rule-name"
    match:
      event_type: "lead.status_changed"
      new_status: "qualified"
    notify: true  # or false to suppress
    channel: "sales"  # logical channel (for future routing)
    template: "[{tenant_id}] Custom message with {actor}"
```

### Default Rules

See `rules.yaml` for current configuration. Examples:

- ✅ **Qualified leads** - Custom template for high-signal status changes
- ✅ **Won deals** - Celebrate closed deals with 💰 emoji
- ✅ **ACME new leads** - Tenant-specific routing
- ✅ **Assignment notifications** - Track ownership changes
- ❌ **Notes suppressed** - Reduce noise from routine comments

### Template Variables

Available in `template` field:
- `{tenant_id}` - Tenant identifier
- `{event_type}` - Event type (lead.created, etc.)
- `{lead_id}` or `{id}` - Lead ID
- `{name}` - Lead name
- `{email}` - Lead email
- `{actor}` - User who triggered the event
- `{old_status}` / `{new_status}` - For status changes
- `{assigned_to}` - For assignments

## Integration Examples

### Slack Webhook

```yaml
environment:
  - NOTIFY_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Microsoft Teams

```yaml
environment:
  - NOTIFY_WEBHOOK=https://outlook.office.com/webhook/YOUR/WEBHOOK/URL
```

### Custom Webhook Server

```python
# Simple webhook receiver for testing
from flask import Flask, request
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(f"📢 {data['text']}")
    return {'status': 'ok'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

Then set:
```yaml
environment:
  - NOTIFY_WEBHOOK=http://host.docker.internal:5001/webhook
```

## Extending

### Add New Event Types

Edit `TOPICS` list in `main.py`:

```python
TOPICS = [
    "apexflow.leads.created",
    "apexflow.leads.status_changed",
    "apexflow.leads.assigned",
    "apexflow.leads.note_added",
    "apexflow.jobs.created",  # Add new topics here
]
```

### Custom Notification Logic

Edit `build_notification()` function:

```python
elif et == "lead.status_changed":
    # Add conditional logic
    if event.get("new_status") == "qualified":
        title = f"🎉 [{tenant_id}] Lead QUALIFIED!"
        message = f"Lead #{lead_id} moved to qualified by {actor}"
    else:
        title = f"[{tenant_id}] Lead #{lead_id} status changed"
        message = f"{actor} changed status {event.get('old_status')} → {event.get('new_status')}"
```

### Add Filtering Rules

Edit `should_notify()` function:

```python
def should_notify(event: Dict[str, Any]) -> bool:
    # Only notify on high-value status changes
    if event.get("event_type") == "lead.status_changed":
        return event.get("new_status") in ("qualified", "won")

    # Always notify on assignments
    if event.get("event_type") == "lead.assigned":
        return True

    return False
```

## Architecture

```
┌─────────────────────────────────────────┐
│  ApexFlow                               │
│  - Creates lead                         │
│  - Changes status                       │
│  - Assigns lead                         │
└─────────────────────────────────────────┘
                  ↓ publishes event
┌─────────────────────────────────────────┐
│  Kafka (Redpanda)                       │
│  - apexflow.leads.created               │
│  - apexflow.leads.status_changed        │
│  - apexflow.leads.assigned              │
│  - apexflow.leads.note_added            │
└─────────────────────────────────────────┘
                  ↓ consumes
┌─────────────────────────────────────────┐
│  Notifications Consumer                 │
│  - Filters by tenant                    │
│  - Applies routing rules                │
│  - Formats message                      │
└─────────────────────────────────────────┘
                  ↓ sends webhook
┌─────────────────────────────────────────┐
│  Slack / Teams / Custom                 │
│  - Receives formatted notification      │
└─────────────────────────────────────────┘
```

## Monitoring

### Logs

```bash
docker logs aether-notifications-consumer -f
```

### Consumer Group Status

```bash
docker exec -it aether-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group aetherlink-notifications \
  --describe
```

## Future Enhancements

- [ ] Rules engine (YAML config)
- [ ] Rate limiting per tenant
- [ ] Retry with exponential backoff
- [ ] Dead letter queue for failed webhooks
- [ ] Template system for message formatting
- [ ] Multiple webhook endpoints per tenant
- [ ] Prometheus metrics (webhooks_sent_total, etc.)
- [ ] Email support (SMTP)
- [ ] SMS support (Twilio)

## License

Part of AetherLink - Multi-tenant event-driven platform
