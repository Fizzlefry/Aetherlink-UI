# 🛠 AetherLink Notifications – Ops Quick Card

**Service:** `aether-notifications-consumer`
**Port:** `9107`
**Config file:** `/app/rules.yaml` (volume-mounted)
**Purpose:** Turn CRM events → human notifications via declarative rules

---

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check → `{ "status": "ok" }` |
| `/rules` | GET | Returns currently loaded rules (live state) |
| `/rules/reload` | POST | Rereads `/app/rules.yaml` and replaces in-memory ruleset |
| `/test-notification` | POST | Feed a fake event to see what would be sent |

---

## Hot-Reload Workflow

```bash
# 1) Edit on host
vim services/notifications-consumer/rules.yaml

# 2) Tell service to reload it
curl -X POST http://localhost:9107/rules/reload

# 3) Confirm
curl http://localhost:9107/rules
```

**No container restart. No rebuild.**

---

## Example Events to Test

### 1. Status → Qualified

```bash
curl -X POST http://localhost:9107/test-notification \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "lead.status_changed",
    "tenant_id": "acme",
    "lead_id": 42,
    "old_status": "contacted",
    "new_status": "qualified",
    "actor": "sarah@acme.com"
  }'
```

**Expected:** `[acme] 🎉 Lead #42 moved to QUALIFIED by sarah@acme.com`

### 2. Deal Won

```bash
curl -X POST http://localhost:9107/test-notification \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "lead.status_changed",
    "tenant_id": "acme",
    "lead_id": 999,
    "old_status": "qualified",
    "new_status": "won",
    "actor": "closer@acme.com"
  }'
```

**Expected:** `[acme] 💰 DEAL WON! Lead #999 closed by closer@acme.com`

### 3. Suppressed Note

```bash
curl -X POST http://localhost:9107/test-notification \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "lead.note_added",
    "tenant_id": "acme",
    "lead_id": 55,
    "body": "this is just a note",
    "actor": "sarah@acme.com"
  }'
```

**Expected:** `{"message":"Notification suppressed by rules"}`
**Log:** `Notification suppressed by rule=suppress-notes`

### 4. Assignment

```bash
curl -X POST http://localhost:9107/test-notification \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "lead.assigned",
    "tenant_id": "acme",
    "lead_id": 123,
    "assigned_to": "jane@acme.com",
    "actor": "manager@acme.com"
  }'
```

**Expected:** `[acme] 👤 Lead #123 assigned to new owner by manager@acme.com`

---

## Typical rules.yaml Shape

```yaml
rules:
  # Suppress noise
  - name: "suppress-notes"
    match:
      event_type: "lead.note_added"
    notify: false

  # High-signal status changes
  - name: "notify-on-qualified"
    match:
      event_type: "lead.status_changed"
      new_status: "qualified"
    notify: true
    channel: "sales"
    template: "[{tenant_id}] 🎉 Lead #{lead_id} moved to QUALIFIED by {actor}"

  - name: "notify-on-won"
    match:
      event_type: "lead.status_changed"
      new_status: "won"
    notify: true
    channel: "sales"
    template: "[{tenant_id}] 💰 DEAL WON! Lead #{lead_id} closed by {actor}"

  # Track assignments
  - name: "notify-on-assignment"
    match:
      event_type: "lead.assigned"
    notify: true
    channel: "assignments"
    template: "[{tenant_id}] 👤 Lead #{lead_id} assigned to new owner by {actor}"

  # Tenant-specific routing
  - name: "acme-new-leads"
    match:
      event_type: "lead.created"
      tenant_id: "acme"
    notify: true
    channel: "acme-leads"
    template: "[{tenant_id}] New lead: {name} ({email}) created by {actor}"

# Fallback for unmatched events
default:
  notify: true
  template: "[{tenant_id}] {event_type} on lead #{lead_id}"
```

---

## Template Variables

Available in `template` field:

| Variable | Description |
|----------|-------------|
| `{tenant_id}` | Tenant identifier |
| `{event_type}` | Event type (lead.created, etc.) |
| `{lead_id}` or `{id}` | Lead ID |
| `{name}` | Lead name |
| `{email}` | Lead email |
| `{actor}` | User who triggered the event |
| `{old_status}` / `{new_status}` | For status changes |
| `{assigned_to}` | For assignments |

---

## Log Enrichment

All notifications include rule name in logs for grep-ability:

```
2025-11-03 22:52:55 INFO Notification matched rule=notify-on-qualified
2025-11-03 22:52:55 INFO Webhook sent (200): [acme] Lead #42 moved to QUALIFIED
```

Or for suppressed events:

```
2025-11-03 22:46:47 INFO Notification suppressed by rule=suppress-notes
```

**Grafana query:**
```
{service="notifications-consumer"} |= "matched rule" | json | count by rule
```

---

## Troubleshooting

### Rules not reloading?

```bash
# Check logs
docker logs aether-notifications-consumer --tail 20

# Verify volume mount
docker inspect aether-notifications-consumer | grep rules.yaml

# Force reload
curl -X POST http://localhost:9107/rules/reload
```

### Webhook not sending?

```bash
# Check webhook URL
docker exec aether-notifications-consumer env | grep NOTIFY_WEBHOOK

# Test with verbose logging
docker logs aether-notifications-consumer -f
```

### Rule not matching?

```bash
# View active rules
curl http://localhost:9107/rules | jq '.rules[] | {name, match}'

# Test event directly
curl -X POST http://localhost:9107/test-notification -d '{"event_type":"..."}'
```

---

## Production Checklist

- [ ] **Webhook configured** - Set `NOTIFY_WEBHOOK` to Slack/Teams/etc.
- [ ] **Rules tested** - Use `/test-notification` to verify behavior
- [ ] **Tenant filter** - Set `TENANT_FILTER` if single-tenant deployment
- [ ] **Volume mounted** - Enable hot-reload with volume mount
- [ ] **Logs monitored** - Send to Loki/Grafana for rule analytics
- [ ] **Health check** - Add to monitoring system

---

## Closed Loop Architecture

```
┌─────────────┐
│  ApexFlow   │ → Publishes events to Kafka
└─────────────┘
       ↓
┌─────────────┐
│   Kafka     │ → apexflow.leads.{created,status_changed,assigned,note_added}
└─────────────┘
       ↓
┌─────────────┐
│ Notif Svc   │ → Applies rules.yaml (hot-reloadable!)
└─────────────┘
       ↓
┌─────────────┐
│ Slack/Teams │ → Human notifications
└─────────────┘
```

**You've now got:**
- ✅ Events come out of AetherLink
- ✅ Rules decide if/what to send
- ✅ Ops can change behavior live
- ✅ Service shows active config

**That's production stuff.** 🚀
