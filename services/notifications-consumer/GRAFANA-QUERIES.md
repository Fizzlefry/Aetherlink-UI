# Grafana Queries for Notifications Service

## Log Enrichment

All notifications include `rule=<rule_name>` in logs for observability.

## Example Queries

### 1. Count Notifications by Rule

**Query:**
```logql
{container_name="aether-notifications-consumer"} |= "Notification matched rule=" | pattern `<_> INFO Notification matched rule=<rule>` | line_format "{{.rule}}"
```

**Panel Type:** Time series  
**Legend:** `{{rule}}`

---

### 2. Suppressed Notifications

**Query:**
```logql
{container_name="aether-notifications-consumer"} |= "Notification suppressed by rule="
```

**Panel Type:** Stat  
**Calculation:** Count

---

### 3. Rule Match Rate

**Query:**
```logql
sum by (rule) (count_over_time({container_name="aether-notifications-consumer"} |= "Notification matched rule=" | pattern `<_> INFO Notification matched rule=<rule>` [5m]))
```

**Panel Type:** Bar chart  
**Legend:** `{{rule}}`

---

### 4. Top Rules (Last 24h)

**Query:**
```logql
topk(5,
  sum by (rule) (
    count_over_time({container_name="aether-notifications-consumer"} |= "Notification matched rule=" | pattern `<_> INFO Notification matched rule=<rule>` [24h])
  )
)
```

**Panel Type:** Table  
**Columns:** Rule, Count

---

### 5. Suppression Rate

**Query:**
```logql
(
  count_over_time({container_name="aether-notifications-consumer"} |= "suppressed by rule=" [5m])
  /
  count_over_time({container_name="aether-notifications-consumer"} |= "Notification" [5m])
) * 100
```

**Panel Type:** Gauge  
**Unit:** Percent (0-100)

---

### 6. Webhook Success Rate

**Query:**
```logql
(
  count_over_time({container_name="aether-notifications-consumer"} |= "Webhook sent (200)" [5m])
  /
  count_over_time({container_name="aether-notifications-consumer"} |= "Webhook sent" [5m])
) * 100
```

**Panel Type:** Stat  
**Unit:** Percent (0-100)  
**Thresholds:** Red < 95, Yellow < 99, Green >= 99

---

### 7. Notifications Timeline

**Query:**
```logql
{container_name="aether-notifications-consumer"} |= "Notification matched rule=" or "Notification suppressed by rule=" | pattern `<timestamp> <level> <message>`
```

**Panel Type:** Logs  
**Show:** timestamp, level, message

---

### 8. Rules Reloaded Events

**Query:**
```logql
{container_name="aether-notifications-consumer"} |= "Rules reloaded:"
```

**Panel Type:** Logs  
**Use Case:** Track when ops team changes rules

---

## Dashboard Layout Example

```
┌─────────────────────────────────────────────────────────┐
│  Notifications by Rule (Time Series)                    │
│  [notify-on-qualified] ────────────────────────         │
│  [notify-on-won] ──────────────                         │
│  [suppress-notes] ────────────────────────────────────  │
└─────────────────────────────────────────────────────────┘

┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐
│ Total Sent       │ │ Suppressed       │ │ Webhook OK   │
│ 1,234            │ │ 567              │ │ 99.2%        │
└──────────────────┘ └──────────────────┘ └──────────────┘

┌─────────────────────────────────────────────────────────┐
│  Top Rules (Bar Chart)                                  │
│  notify-on-qualified  ████████████████ 543              │
│  notify-on-assignment ████████ 234                      │
│  notify-on-won        █████ 123                         │
│  default              ███ 67                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Recent Notifications (Logs)                            │
│  23:00:50 INFO Notification matched rule=default        │
│  23:00:43 INFO Notification matched rule=notify-on-...  │
│  23:00:37 INFO Notification matched rule=notify-on-won  │
└─────────────────────────────────────────────────────────┘
```

---

## Alerts

### High Suppression Rate

```yaml
alert: HighNotificationSuppressionRate
expr: |
  (
    rate({container_name="aether-notifications-consumer"} |= "suppressed by rule=" [5m])
    /
    rate({container_name="aether-notifications-consumer"} |= "Notification" [5m])
  ) > 0.8
for: 10m
labels:
  severity: warning
annotations:
  summary: "Over 80% of notifications are being suppressed"
  description: "Check if rules.yaml is too aggressive"
```

### Webhook Failures

```yaml
alert: NotificationWebhookFailures
expr: |
  rate({container_name="aether-notifications-consumer"} |= "Webhook sent" != "200" [5m]) > 0
for: 5m
labels:
  severity: critical
annotations:
  summary: "Notification webhooks are failing"
  description: "Check NOTIFY_WEBHOOK endpoint health"
```

### No Notifications Sent

```yaml
alert: NoNotificationsSent
expr: |
  absent_over_time({container_name="aether-notifications-consumer"} |= "Notification matched rule=" [15m])
for: 15m
labels:
  severity: warning
annotations:
  summary: "No notifications sent in 15 minutes"
  description: "Check if Kafka consumer is connected"
```

---

## Sample Log Output

```
2025-11-03 23:00:17,629 INFO Notification suppressed by rule=suppress-notes
2025-11-03 23:00:29,442 INFO Notification matched rule=notify-on-qualified
2025-11-03 23:00:29,449 INFO Webhook sent (405): lead.status_changed (acme)
2025-11-03 23:00:37,144 INFO Notification matched rule=notify-on-won
2025-11-03 23:00:37,146 INFO Webhook sent (405): lead.status_changed (acme)
2025-11-03 23:00:43,888 INFO Notification matched rule=notify-on-assignment
2025-11-03 23:00:43,891 INFO Webhook sent (405): lead.assigned (widgets-r-us)
2025-11-03 23:00:50,818 INFO Notification matched rule=default
2025-11-03 23:00:50,820 INFO Webhook sent (405): lead.created (widgets-r-us)
```

**Pattern:** Every notification includes `rule=<name>` for grep/query

---

## Benefits

- ✅ **Rule Performance** - See which rules fire most often
- ✅ **Noise Detection** - Track suppression rates
- ✅ **Webhook Health** - Monitor delivery success
- ✅ **Operational Visibility** - Know when rules change
- ✅ **Debugging** - Trace why specific events matched/suppressed
- ✅ **Capacity Planning** - Understand notification volume by rule
