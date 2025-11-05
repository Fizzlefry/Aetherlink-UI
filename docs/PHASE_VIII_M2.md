# Phase VIII M2: Alert Rule Templates

**Date:** 2025-11-04
**Status:** ✅ Complete
**Version:** Unreleased (post v1.21.0, follows M1)

## Overview

Pre-built alert rule templates that operators can materialize into real alert rules with one click. Transforms the Operator Dashboard from read-only monitoring into an actionable control plane.

## What This Adds

### Backend: Alert Templates Router
- **routers/alert_templates.py** - New FastAPI router for template CRUD
- **In-memory template registry** (TEMPLATES_DB dict) - Can be migrated to SQLite if needed
- **5 default templates** seeded on startup

### Template Operations
- `GET /alerts/templates` - List all templates (tenant-filterable)
- `POST /alerts/templates` - Create new template
- `GET /alerts/templates/{id}` - Get specific template
- `PUT /alerts/templates/{id}` - Update template
- `DELETE /alerts/templates/{id}` - Delete template
- `POST /alerts/templates/{id}/materialize` - Create real alert rule from template

### UI: Template Management Panel
- **Alert Rule Templates section** in OperatorDashboard.tsx
- **One-click materialization** - "Create Rule" button per template
- **Tenant-aware** - Uses current tenant filter when creating rules
- **Auto-refresh** - Fetches templates every 30s alongside other dashboard data

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Operator Dashboard (React)                              │
│   📋 Alert Rule Templates Section                       │
│     ├─ List templates (filtered by tenant)             │
│     ├─ Show: name, event type, severity, threshold     │
│     └─ "Create Rule" button → materialize endpoint     │
└─────────────────────────────────────────────────────────┘
                      ↓ POST /alerts/templates/{id}/materialize
┌─────────────────────────────────────────────────────────┐
│ Command Center API                                      │
│   alert_templates.py Router                            │
│     ├─ materialize_template()                          │
│     ├─ Reads template definition                       │
│     ├─ Calls alert_store.create_rule()                 │
│     └─ Returns created rule                            │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ Alert Store (SQLite)                                    │
│   alert_rules table                                     │
│     ├─ New rule inserted with [tpl] prefix             │
│     ├─ Inherits tenant_id from request or template     │
│     └─ Monitored by alert_evaluator_loop()             │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ Alert Evaluator (Background Worker)                     │
│   Evaluates new rule every 15s                          │
│     ├─ Checks event_store for threshold violations     │
│     ├─ Enqueues alerts to delivery_queue               │
│     └─ Reliable delivery via Phase VII M5 system       │
└─────────────────────────────────────────────────────────┘
```

## Default Templates Seeded

1. **Alert Delivery Failures**
   - Triggers: `ops.alert.delivery.failed` events
   - Severity: error
   - Threshold: 1 in 300s
   - Use case: Dead letter notifications when webhooks fail after all retries

2. **High Error Rate**
   - Triggers: Any event with severity=error
   - Threshold: 10 in 300s (5 minutes)
   - Use case: Spike detection across all services

3. **Critical Events**
   - Triggers: Any event with severity=critical
   - Threshold: 1 in 60s (immediate)
   - Use case: Urgent notifications for critical issues

4. **AutoHeal Failures**
   - Triggers: `autoheal.failed` events from aether-auto-heal
   - Severity: warning
   - Threshold: 3 in 600s (10 minutes)
   - Use case: Auto-healing system monitoring

5. **Event Retention Issues**
   - Triggers: `ops.events.prune.failed` events
   - Severity: warning
   - Threshold: 1 in 3600s (1 hour)
   - Use case: Database maintenance monitoring

## Template Schema

```typescript
type AlertTemplate = {
  id: string;                    // UUID
  name: string;                  // Display name
  description?: string;          // What this template does
  event_type: string;            // Event type to match (or null for any)
  source?: string | null;        // Source service filter
  severity: string;              // Event severity (info, warning, error, critical)
  window_seconds: number;        // Time window for threshold
  threshold: number;             // Event count to trigger alert
  target_webhook?: string;       // Webhook URL (reference only)
  target_channel?: string;       // Channel name (e.g., #ops)
  tenant_id?: string | null;     // Optional tenant restriction
  created_at: string;            // ISO timestamp
  updated_at: string;            // ISO timestamp
};
```

## Materialization Flow

**Operator Action:**
1. Navigate to Operator Dashboard → 📊 Operator tab
2. Scroll to "Alert Rule Templates" section
3. Select tenant filter (e.g., "tenant-qa")
4. Click "Create Rule" on desired template

**Backend Processing:**
```python
# 1. Fetch template definition
tpl = TEMPLATES_DB[template_id]

# 2. Build alert rule from template
rule_name = f"[tpl] {tpl['name']}"  # Prefix indicates template origin
tenant_id = request.tenant_id or tpl.tenant_id

# 3. Create rule via alert_store
rule_id = alert_store.create_rule(
    name=rule_name,
    severity=tpl['severity'],
    event_type=tpl['event_type'],
    source=tpl['source'],
    window_seconds=tpl['window_seconds'],
    threshold=tpl['threshold'],
    enabled=True,
    tenant_id=tenant_id
)

# 4. Return created rule
return {"rule_id": rule_id, "rule": created_rule}
```

**Result:**
- New alert rule appears in alert_rules table
- Alert evaluator picks it up in next 15s cycle
- When threshold exceeded → enqueues to delivery_queue
- Reliable delivery via Phase VII M5 exponential backoff system

## UI Features

### Template Table Columns
- **Name** - Template name + description
- **Event Type** - Event type filter (shown as code block)
- **Severity** - Color-coded severity badge
- **Threshold** - "N in Xs" format (e.g., "10 in 300s")
- **Target** - Webhook URL (truncated) or channel name
- **Tenant** - Tenant restriction (or "any")
- **Action** - Blue "Create Rule" button

### Color Coding
- **Critical** - Dark red background, red text, red border
- **Error** - Red background, red text
- **Warning** - Yellow background, yellow text
- **Info** - Slate background, gray text

### User Experience
- **One-click creation** - No forms, instant materialization
- **Tenant-aware** - Respects current tenant filter
- **Success feedback** - Alert shows rule ID and name
- **Error handling** - Alert shows error message if creation fails
- **Auto-refresh** - Template list updates every 30s

## API Examples

### List Templates
```bash
GET /alerts/templates
Headers: X-User-Roles: operator

Response:
{
  "status": "ok",
  "count": 5,
  "templates": [
    {
      "id": "abc-123",
      "name": "Alert Delivery Failures",
      "description": "Notify when webhook deliveries fail after all retries",
      "event_type": "ops.alert.delivery.failed",
      "severity": "error",
      "window_seconds": 300,
      "threshold": 1,
      "target_channel": "#aether-ops",
      "tenant_id": null,
      "created_at": "2025-11-04T10:00:00Z"
    }
  ]
}
```

### Materialize Template
```bash
POST /alerts/templates/abc-123/materialize
Headers:
  X-User-Roles: operator
  Content-Type: application/json
Body:
{
  "tenant_id": "tenant-qa",
  "enabled": true
}

Response:
{
  "status": "ok",
  "template_id": "abc-123",
  "rule_id": 42,
  "rule": {
    "id": 42,
    "name": "[tpl] Alert Delivery Failures",
    "event_type": "ops.alert.delivery.failed",
    "severity": "error",
    "window_seconds": 300,
    "threshold": 1,
    "tenant_id": "tenant-qa",
    "enabled": true,
    "created_at": "2025-11-04T11:30:00Z"
  }
}
```

## Testing

```bash
# 1. Start Command Center with v1.21.0+ (includes M1 dashboard)
cd deploy
docker-compose -f docker-compose.dev.yml up command-center

# 2. Verify templates seeded
curl http://localhost:8010/alerts/templates \
  -H "X-User-Roles: operator"
# Should return 5 default templates

# 3. Start UI
cd services/ui
npm run dev

# 4. Navigate to Operator Dashboard
open http://localhost:5173
# Click "📊 Operator" tab
# Scroll to "Alert Rule Templates" section

# 5. Test materialization
# - Select tenant filter (e.g., "tenant-qa")
# - Click "Create Rule" on "High Error Rate" template
# - Should see alert: "✅ Alert rule created from template!"

# 6. Verify rule created
curl http://localhost:8010/alerts/rules \
  -H "X-User-Roles: operator"
# Should see new rule with name "[tpl] High Error Rate"

# 7. Verify rule is active
# - Publish 10+ error events for tenant-qa within 5 minutes
# - Alert evaluator should trigger rule
# - Alert should be enqueued to delivery_queue
# - Check /alerts/deliveries to see pending delivery
```

## Benefits

**Before Phase VIII M2:**
```bash
# Operators had to manually create alert rules
curl -X POST http://localhost:8010/alerts/rules \
  -H "X-User-Roles: operator" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Error Rate",
    "event_type": null,
    "severity": "error",
    "window_seconds": 300,
    "threshold": 10,
    "enabled": true
  }'
# 😓 Complex, error-prone, requires API knowledge
```

**After Phase VIII M2:**
```
1. Click "📊 Operator" tab
2. Scroll to "Alert Rule Templates"
3. Click "Create Rule" on "High Error Rate"
✨ Done! Rule is live and monitoring.
```

## Integration with Phase VII M5

Templates create alert rules that use the reliable delivery system:

```
Template Materialized
  ↓
New Alert Rule Created
  ↓
Alert Evaluator Monitors Rule (every 15s)
  ↓
Threshold Exceeded → ops.alert.raised emitted
  ↓
Check Dedup Window (5 minutes per rule+tenant)
  ↓
Enqueue to alert_delivery_queue
  ↓
Delivery Dispatcher Attempts Webhook POST
  ↓
Success → DELETE from queue ✅
Failure → Exponential backoff + retry 🔄
Max Attempts → ops.alert.delivery.failed ☠️
```

All benefits from Phase VII M5 apply:
- **Durable** - Queued in SQLite
- **Retryable** - Background dispatcher with backoff
- **Non-spammy** - Dedup per rule + tenant
- **Observable** - Delivery stats + dead-letter events

## Files Modified

- **services/command-center/routers/alert_templates.py** (NEW) - Template CRUD + materialization
- **services/command-center/main.py** (MODIFIED) - Import router, seed templates on startup
- **services/ui/src/pages/OperatorDashboard.tsx** (MODIFIED) - Added templates section with materialization

## Future Enhancements (Post-M2)

1. **Template Import/Export** - JSON file format for sharing templates
2. **Template Versioning** - Track template changes over time
3. **Bulk Materialization** - Create rules for multiple tenants at once
4. **Template Testing** - Preview what events would trigger template
5. **Custom Templates** - UI form for creating new templates (currently API-only)
6. **Template Categories** - Group templates by use case (errors, performance, security)

## Notes

- Templates are **not** alert rules - they're blueprints
- Materializing a template creates a real alert rule in alert_rules table
- Deleting a template does not affect rules created from it
- Template modifications do not affect existing rules (intentional - rules are independent)
- `[tpl]` prefix in rule name indicates template origin (helps operators identify source)
- Tenant restriction in template is a suggestion - operator can override during materialization

## Result

Operators can now:
1. **Monitor** delivery queue health (Phase VIII M1)
2. **Act** by creating alert rules with one click (Phase VIII M2) ← NEW

The Operator Dashboard is no longer just a read-only view - it's now a **control plane** for the Event Control Plane. 🎛️
