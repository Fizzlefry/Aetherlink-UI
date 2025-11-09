# AetherLink MCP Tools Reference

Quick reference for AI assistants using the AetherLink MCP server.

## Tool Summary

The MCP server exposes **4 tools** for monitoring and managing AetherLink operations:

1. **`aetherlink.get_ops_snapshot`** - 📊 Read: Full ops state (anomalies + deliveries + recommendations)
2. **`aetherlink.get_anomalies`** - 🚨 Read: Current anomaly detection results
3. **`aetherlink.get_deliveries`** - 📮 Read: Recent delivery history
4. **`aetherlink.replay_delivery`** - 🔄 Write: Replay a failed/pending delivery

## Usage Guidelines for AI Assistants

### When to call which tool:

**Default check (90% of cases):**
```
→ aetherlink.get_ops_snapshot
```
This gives you everything: health, anomalies, deliveries, and actionable recommendations.

**Focused investigation:**
```
User asks: "What anomalies are there?"
→ aetherlink.get_anomalies

User asks: "Show me recent deliveries"
→ aetherlink.get_deliveries
```

**Taking action:**
```
User says: "Replay that delivery" or "Retry the failed one"
→ aetherlink.replay_delivery(delivery_id="...")
```

### Decision Tree

```
User query about AetherLink ops?
├─ YES → Call aetherlink.get_ops_snapshot
│   └─ Check response:
│       ├─ anomalies.critical > 0? → ⚠️  Mention first
│       ├─ deliveries.failed > 0?  → 📮 Suggest replay
│       └─ Otherwise              → ✅ Report healthy
│
└─ User asks to replay?
    └─ Call aetherlink.replay_delivery(delivery_id)
```

## Tool Details

### 1. `aetherlink.get_ops_snapshot`

**Purpose:** Get comprehensive ops state with AI-friendly formatting

**Parameters:**
```json
{
  "min_severity": "info" | "warning" | "critical"  // optional, default: "info"
}
```

**When to use:**
- User asks "What's the status?"
- User asks "Any issues?"
- User asks "Check AetherLink"
- Default: Always start here

**Response includes:**
- `timestamp` - When snapshot was taken
- `health` - Overall health status
- `anomalies` - Detected issues (spikes, drops, errors)
  - `total`, `critical`, `warnings` counts
  - `incidents[]` - Details of each anomaly
- `deliveries` - Recent delivery attempts
  - `problematic` - Count of failed/pending/dead_letter
  - `items[]` - Details of problematic deliveries
- `recommendations[]` - Actionable next steps
  - `priority` - high/medium/low
  - `message` - What to do
  - `action` - How to do it

**Example call:**
```json
{
  "name": "aetherlink.get_ops_snapshot",
  "arguments": {
    "min_severity": "warning"
  }
}
```

**How to interpret response:**

```javascript
if (response.anomalies.critical > 0) {
  // 🚨 URGENT: Mention critical anomalies first
  // Show: incident message, affected tenant, metric details
}

if (response.deliveries.failed > 0) {
  // 📮 IMPORTANT: Failed deliveries need attention
  // Suggest: Review error messages, consider replay
}

if (response.deliveries.dead_letter > 0) {
  // ⚠️  CRITICAL: Max retries exceeded
  // Action: Manual investigation required before replay
}

// Always show recommendations
response.recommendations.forEach(rec => {
  // Display with priority indicator
  // [HIGH] / [MEDIUM] / [LOW]
})
```

---

### 2. `aetherlink.get_anomalies`

**Purpose:** Get current anomaly detection results only

**Parameters:** None

**When to use:**
- User specifically asks about anomalies
- Follow-up after ops_snapshot shows anomalies.total > 0
- Detailed anomaly investigation

**Response includes:**
- `incidents[]` - Array of detected anomalies
  - `type` - spike, drop, error_rate, tenant_isolation
  - `severity` - critical, warning
  - `metric_name` - Which metric triggered
  - `baseline_value` - Expected value
  - `current_value` - Actual value
  - `delta_percent` - % change from baseline
  - `message` - Human-readable summary
  - `affected_tenant` - Which tenant (if any)
  - `affected_endpoint` - Which endpoint (if any)
- `summary` - Aggregate counts
- `window_minutes` - Detection window size
- `baseline_minutes` - Baseline comparison window

**Example response:**
```json
{
  "incidents": [
    {
      "type": "spike",
      "severity": "critical",
      "metric_name": "error_rate",
      "baseline_value": 5,
      "current_value": 25,
      "delta_percent": 400,
      "message": "Error rate spike: 400% above baseline",
      "affected_tenant": "tenant-qa"
    }
  ],
  "summary": {
    "total_incidents": 1,
    "critical_incidents": 1,
    "warning_incidents": 0
  }
}
```

---

### 3. `aetherlink.get_deliveries`

**Purpose:** Get recent delivery history

**Parameters:**
```json
{
  "limit": 20  // optional, default: 20, max number to return
}
```

**When to use:**
- User asks "Show me deliveries"
- User asks "What failed?"
- Follow-up after ops_snapshot shows deliveries.problematic > 0

**Response includes:**
- `items[]` - Array of delivery attempts
  - `id` - Delivery UUID (use for replay)
  - `status` - delivered, failed, pending, dead_letter
  - `rule_name` - Which alert rule triggered this
  - `event_type` - Event that triggered the alert
  - `tenant_id` - Which tenant
  - `target` - Destination URL (webhook)
  - `attempts` - Current retry count
  - `max_attempts` - Maximum retries allowed
  - `last_error` - Error message (if failed)
  - `next_retry_at` - When next retry is scheduled
  - `created_at` - When delivery was created
  - `updated_at` - When last updated

**Status meanings:**
- `delivered` ✅ - Successfully sent
- `failed` ⚠️  - Failed, will retry
- `pending` ⏳ - Queued, not yet attempted
- `dead_letter` 🛑 - Max retries exceeded, manual intervention needed

---

### 4. `aetherlink.replay_delivery`

**Purpose:** Retry a failed or pending delivery

**Parameters:**
```json
{
  "delivery_id": "uuid-string"  // REQUIRED
}
```

**When to use:**
- User says "Replay that delivery"
- User says "Retry the failed one"
- After reviewing a failed delivery, user approves retry
- **IMPORTANT:** Get user confirmation before replaying

**Safety checks (you should do):**
1. Check delivery status first (via get_ops_snapshot or get_deliveries)
2. If `dead_letter` → warn user, ask for confirmation
3. If error is not transient (auth, config) → suggest fixing root cause first
4. If `attempts` >= `max_attempts` → warn user

**Example safe workflow:**
```
User: "Replay the failed delivery"

AI: [Calls get_ops_snapshot to see current state]
AI: I found delivery abc-123 with status "failed" (3/5 attempts).
    Error: "HTTP 503: Service Unavailable"

    This appears to be a transient error. Safe to replay. Proceed?

User: "Yes"

AI: [Calls replay_delivery with delivery_id="abc-123"]
AI: ✅ Delivery queued for replay. It will retry with exponential backoff.
```

**Error handling:**
```javascript
if (error.code === -32602) {
  // Missing delivery_id parameter
  // Ask user which delivery to replay
}

if (error.code === -32000 && error.message.includes("404")) {
  // Delivery not found
  // Check if delivery_id is correct
}

if (error.code === -32000 && error.message.includes("already delivered")) {
  // Delivery already succeeded
  // No action needed
}
```

---

## Response Formatting Guidelines

### For ops_snapshot responses:

**If healthy:**
```
✅ All systems healthy
- 0 anomalies detected
- 0 failed deliveries
- No action required
```

**If issues detected:**
```
⚠️  Issues detected in AetherLink:

Anomalies (2):
🔴 CRITICAL: Error rate spike: 400% above baseline
   Tenant: tenant-qa
   Metric: error_rate (baseline: 5, current: 25)

🟡 WARNING: Response time increase: 150% above baseline
   Endpoint: /api/events

Deliveries (3 problematic):
❌ 2 failed deliveries
⏳ 1 pending delivery

Recent failures:
- [tenant-qa] Alert Delivery Failures
  Error: HTTP 503: Service Unavailable from Slack
  Attempts: 3/5
  ID: 4a142c00-aa0e-43cb-aac7-f85bf5aef14f

Recommendations:
🔴 [HIGH] 1 critical anomalies detected. Investigate immediately.
🟡 [MEDIUM] 2 failed deliveries found. Consider replaying.
```

### For anomaly responses:

```
🚨 Anomaly Detection Results:

Critical (1):
- Error rate spike: 400% above baseline
  Tenant: tenant-qa
  Current: 25 errors (baseline: 5)

Warnings (1):
- Response time increase: 150% above baseline
  Endpoint: /api/events
  Current: 750ms (baseline: 300ms)
```

### For delivery responses:

```
📮 Recent Deliveries:

Failed (2):
1. [tenant-qa] Alert Delivery Failures
   Error: HTTP 503: Service Unavailable
   Attempts: 3/5
   ID: abc-123

2. [tenant-qa] High Error Rate
   Error: Max attempts reached - dead lettered
   Attempts: 5/5
   ID: def-456

Pending (1):
3. [tenant-qa] System Alert
   Next retry: 2025-11-06T04:30:00Z
   ID: ghi-789
```

### For replay responses:

```
✅ Delivery abc-123 queued for replay
- Status: Will retry with exponential backoff
- Current attempts: 3/5
- Expected retry: Within 5 minutes
```

## Error Scenarios

### Network errors
```
User: "Check ops status"
AI: [Calls get_ops_snapshot]
AI: ❌ Unable to connect to AetherLink:
    - Bridge error: Connection refused
    - The AI Agent Bridge may be offline
    - Check if services are running on localhost:3001
```

### No data
```
User: "What anomalies?"
AI: [Calls get_anomalies]
AI: ✅ No anomalies detected in the last 5 minutes
    - All metrics within normal ranges
    - System is healthy
```

### Invalid replay attempt
```
User: "Replay delivery xyz"
AI: [Calls replay_delivery]
AI: ❌ Replay failed: Delivery xyz-999 not found
    - Please verify the delivery ID
    - Use get_deliveries to see available deliveries
```

## Best Practices

1. **Always start with get_ops_snapshot** - It's optimized for AI consumption
2. **Check severity** - Mention critical issues first
3. **Be actionable** - Always suggest next steps from recommendations
4. **Confirm before replay** - Especially for dead_letter status
5. **Show context** - Include tenant, error message, attempt count
6. **Use emojis** - Makes status easier to scan (✅ 🚨 ⚠️ 📮 🔴 🟡)
7. **Format IDs** - Truncate long UUIDs in summaries (abc-123... instead of full UUID)

## Common Patterns

### Health check
```
User: "How's AetherLink?"
→ get_ops_snapshot
→ Show summary + recommendations
```

### Investigation
```
User: "Why are deliveries failing?"
→ get_ops_snapshot (to see failures)
→ Show delivery details with errors
→ Suggest root cause based on error messages
```

### Remediation
```
User: "Fix the failed deliveries"
→ get_ops_snapshot (to see current state)
→ Check each failed delivery
→ For transient errors (503, timeout): Offer replay
→ For permanent errors (401, 404): Suggest config fix
→ For dead_letter: Warn and ask confirmation
```

### Monitoring
```
User: "Keep an eye on AetherLink"
→ get_ops_snapshot (initial state)
→ Explain monitoring approach
→ Suggest setting up alerts
→ Offer to check periodically
```

## Version Info

- MCP Server: 1.0.0
- Protocol: JSON-RPC 2.0
- Transport: stdio
- Node Version: 18+
