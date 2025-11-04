# CRM Finance Alerts — Runbook

**Service**: CRM Portal  
**Component**: Finance & Payments  
**Team**: Engineering / Finance Ops  
**Last Updated**: November 2, 2025

---

## Overview

This runbook covers the 3 critical finance alerts for the CRM system:

1. **LowInvoicePaymentRate** (Warning) — Payment conversion rate below 50%
2. **RevenueZeroStreak** (Critical) — No revenue recorded for 48 hours
3. **InvoiceGenerationStalled** (Warning) — No invoices created during business hours

All alerts are configured in `monitoring/prometheus-alerts.yml` and route to `#crm-alerts` Slack channel.

---

## Alert 1: LowInvoicePaymentRate (Warning)

### Meaning
Invoice payment rate has dropped below 50% over a 30-day rolling window.

**Formula**: `paid_invoices / created_invoices < 0.50`

### When It Fires
- **Threshold**: Payment rate < 50%
- **Duration**: 24 hours
- **Severity**: Warning
- **Expected Rate**: ≥50% (healthy), ≥85% (excellent)

### Symptoms
- Grafana "Invoice Payment Rate (30d)" gauge shows red/orange
- `crm_invoices_paid_total` growing slower than `crm_invoices_generated_total`
- Cash flow projections missing targets

### Diagnostic Steps

**1. Check Current Payment Rate**
```bash
# Grafana
http://localhost:3000/d/peakpro_crm_kpis → "Invoice Payment Rate (30d)" panel

# Prometheus (raw query)
curl -s 'http://localhost:9099/api/v1/query?query=crm:payment_rate_30d_pct' | jq '.data.result[0].value[1]'
```

**2. Check Invoice Volumes**
```bash
# Created in last 30 days
curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoices_generated_total[30d]))' | jq

# Paid in last 30 days
curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoices_paid_total[30d]))' | jq
```

**3. Verify QuickBooks Connection**
```bash
# Check QBO OAuth status
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status

# Expected: {"connected": true, "realm_id": "...", "env": "sandbox"}
```

**4. Check Invoice Status Poller Health**
```bash
# Confirm poller is running
docker logs crm-api | grep -i "invoice status poller"

# Expected: "INFO - Starting invoice status poller (interval: 30min)"

# Check for polling errors
docker logs crm-api | grep -i "poll_invoice_status" | tail -20
```

**5. Review Unpaid Invoices**
```bash
# Query database for open invoices
docker exec postgres-crm psql -U crm -d crm -c "
  SELECT id, qbo_invoice_number, qbo_status, qbo_balance_cents, qbo_last_sync_at
  FROM leads
  WHERE qbo_invoice_id IS NOT NULL
    AND qbo_status != 'Paid'
  ORDER BY qbo_last_sync_at DESC
  LIMIT 10;
"
```

### Resolution Steps

**Scenario A: QBO Not Connected**
```bash
# Reconnect QuickBooks OAuth
open http://localhost:8089/qbo/oauth/start

# Follow authorization flow, verify connection
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status
```

**Scenario B: Poller Stopped Running**
```bash
# Restart CRM API
docker compose restart crm-api

# Wait 30 seconds, confirm poller started
docker logs crm-api --tail 20 | grep "invoice status poller"
```

**Scenario C: Customer Follow-Up Needed**
1. Export unpaid invoices from CRM: `GET /leads?qbo_status=Open`
2. Review customer communication sequences
3. Send payment reminders via CRM or manually
4. Update payment terms if friction identified (e.g., net-30 → net-15)

**Scenario D: QuickBooks Sandbox Data**
- Dev/staging environments use QBO sandbox with test data
- Payment rate may be artificially low due to incomplete test flows
- **Action**: Acknowledge alert, document expected behavior in test environments

### Prevention
- Set up automated payment reminder emails (7 days, 14 days, 30 days overdue)
- Implement customer payment plan options for large invoices
- Monitor payment rate weekly (not just when alert fires)
- Configure invoice due dates appropriately (net-15, net-30)

### Escalation
- **Warning level**: Investigate within 4 hours during business hours
- **If rate drops below 30%**: Escalate to Finance Manager
- **If systemic issue**: Page on-call engineer for CRM service

---

## Alert 2: RevenueZeroStreak (Critical)

### Meaning
No invoice payments have been recorded for 48 consecutive hours. This indicates a critical failure in the payment tracking pipeline.

**Formula**: `sum(increase(crm_invoice_payments_cents_total[48h])) == 0`

### When It Fires
- **Threshold**: Zero revenue for 48 hours
- **Duration**: 48 hours
- **Severity**: Critical
- **Expected**: Revenue should flow daily during business operations

### Symptoms
- Grafana "Revenue (7 days)" chart flat-lines
- `crm_invoice_payments_cents_total` counter not incrementing
- No `invoice_paid` activity logs in database

### Diagnostic Steps

**1. Check Metrics Endpoint**
```bash
# Verify metric exists and is incrementing
curl -s http://localhost:8089/metrics | grep crm_invoice_payments_cents_total

# Expected: crm_invoice_payments_cents_total{org_id="1"} 250000.0
# If missing or not incrementing → metric collection broken
```

**2. Verify QBO Connection**
```bash
# Check OAuth status
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status

# If disconnected: {"connected": false, "error": "No tokens found"}
```

**3. Check Invoice Poller Logs**
```bash
# Look for polling activity
docker logs crm-api | grep "poll_invoice_status" | tail -50

# Check for API errors
docker logs crm-api | grep -i "qbo.*error" | tail -20

# Expected: Regular polling logs every 30 minutes, no errors
```

**4. Verify Invoices Exist**
```bash
# Query invoices in CRM
docker exec postgres-crm psql -U crm -d crm -c "
  SELECT COUNT(*) as total_invoices,
         COUNT(CASE WHEN qbo_status = 'Paid' THEN 1 END) as paid_count
  FROM leads
  WHERE qbo_invoice_id IS NOT NULL;
"
```

**5. Test Manual Polling**
```bash
# Trigger manual invoice status check
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8089/qbo/sync/invoice/poll_all"

# Check response and logs
docker logs crm-api --tail 30 | grep "poll_invoice_status"
```

### Resolution Steps

**Scenario A: QBO OAuth Expired**
```bash
# Reconnect QuickBooks
open http://localhost:8089/qbo/oauth/start

# Complete OAuth flow
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status

# Manually trigger poll to resume
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8089/qbo/sync/invoice/poll_all"
```

**Scenario B: Background Poller Crashed**
```bash
# Check if poller is running
docker logs crm-api | grep "invoice status poller" | tail -5

# If not found or stale, restart API
docker compose restart crm-api

# Wait 60 seconds, verify poller restarted
docker logs crm-api --tail 20 | grep "Starting invoice status poller"
```

**Scenario C: QuickBooks API Down**
```bash
# Check QuickBooks API status
curl -I https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice

# Check QBO status page: https://status.developer.intuit.com

# If QBO is down: Wait for resolution, alert will auto-resolve when polling resumes
```

**Scenario D: Metric Collection Broken**
```bash
# Verify Prometheus scraping CRM API
curl -s http://localhost:9099/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="crm-api")'

# If unhealthy: Check network, confirm port 8089 accessible
# Restart Prometheus if needed
docker compose restart prometheus
```

**Scenario E: Database Connection Issues**
```bash
# Check CRM API database connectivity
docker logs crm-api | grep -i "database\|postgres" | tail -20

# Test database connection
docker exec postgres-crm psql -U crm -d crm -c "SELECT 1;"

# If connection issues: Restart postgres-crm container
docker compose restart postgres-crm crm-api
```

### Prevention
- Monitor QBO OAuth token expiry (refresh tokens expire after 100 days)
- Set up health checks for background poller (heartbeat metric)
- Configure retry logic for QBO API calls with exponential backoff
- Add redundant revenue tracking via Stripe webhooks (cross-validation)

### Escalation
- **Critical alert**: Page on-call engineer immediately
- **Business hours**: Engineering Manager + Finance Manager notified
- **If unresolved in 2 hours**: Escalate to CTO

---

## Alert 3: InvoiceGenerationStalled (Warning)

### Meaning
No invoices have been created in the last 24 hours during business hours (8am-6pm). May indicate broken automation or expected downtime.

**Formula**: `sum(increase(crm_invoices_generated_total[24h])) == 0 AND hour() >= 8 AND hour() <= 18`

### When It Fires
- **Threshold**: Zero invoices created in 24 hours
- **Duration**: 24 hours (during business hours only)
- **Severity**: Warning
- **Expected**: At least 1-5 invoices/day during normal operations

### Symptoms
- Grafana "Invoices Created (24h)" panel shows 0
- `crm_invoices_generated_total` counter stagnant
- No new invoices visible in QuickBooks Online

### Diagnostic Steps

**1. Check Invoice Creation Metric**
```bash
# Query 24h invoice count
curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoices_generated_total[24h]))' | jq

# Expected: > 0 during normal operations
```

**2. Verify Stripe Webhook Flow**
```bash
# Check recent payment webhook events
docker logs crm-api | grep "payment_intent.succeeded" | tail -10

# Expected: Webhook received → auto-invoice triggered
```

**3. Check Auto-Invoice Background Task**
```bash
# Look for invoice creation attempts
docker logs crm-api | grep -i "create.*invoice\|qbo.*invoice" | tail -30

# Check for errors
docker logs crm-api | grep -i "error.*invoice" | tail -20
```

**4. Review Proposal Pipeline**
```bash
# Check if proposals exist and are approved
docker exec postgres-crm psql -U crm -d crm -c "
  SELECT status, COUNT(*) as count
  FROM leads
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY status;
"

# Expected: Some proposals in 'approved' status
```

**5. Verify QBO Connection**
```bash
# Check QuickBooks OAuth
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status

# If disconnected, invoices cannot be created
```

### Resolution Steps

**Scenario A: Weekend/Holiday (Expected)**
- Alert fires outside business operations (weekends, holidays)
- **Action**: Acknowledge alert, document expected downtime
- **Fix**: Adjust alert query to exclude weekends: `AND day_of_week() <= 5`

**Scenario B: No Approved Proposals**
- No proposals have reached "approved" status to trigger invoicing
- **Action**: Review sales pipeline, confirm lead conversion funnel working
- **Fix**: None needed if low activity is expected (e.g., early-stage startup)

**Scenario C: Stripe Webhook Not Firing**
```bash
# Check Stripe webhook logs in Stripe Dashboard
open https://dashboard.stripe.com/test/webhooks

# Verify webhook endpoint configured: POST /payments/webhook
# Re-send test webhook from Stripe Dashboard

# Check CRM API received it
docker logs crm-api | grep "webhook" | tail -20
```

**Scenario D: QBO Auto-Invoice Disabled**
```bash
# Check environment variable
docker exec crm-api printenv | grep QBO

# Verify QBO_CLIENT_ID and QBO_CLIENT_SECRET set
# If missing: Add to docker-compose.yml and restart
```

**Scenario E: Background Task Crashed**
```bash
# Check if auto-invoice task is running
docker logs crm-api | grep "auto.*invoice\|background.*invoice" | tail -20

# Restart CRM API to recover
docker compose restart crm-api
```

### Prevention
- Set up monitoring for proposal→payment→invoice conversion rates
- Add health check endpoint: `GET /health` returns invoice generation status
- Configure Stripe webhook monitoring (alert if webhooks fail for >1 hour)
- Document expected low-activity periods (holidays, weekends)

### Escalation
- **Warning level**: Review during next business day
- **If proposals exist but invoices not generating**: Escalate to Engineering within 4 hours
- **If customer payments affected**: Urgent escalation to Finance + Engineering

---

## Quick Reference Commands

### Health Checks
```bash
# CRM API health
curl http://localhost:8089/metrics | head -20

# QuickBooks connection
curl -H "Authorization: Bearer $TOKEN" http://localhost:8089/qbo/status

# Prometheus targets
curl -s http://localhost:9099/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="crm-api")'

# Active alerts
curl -s http://localhost:9099/api/v1/alerts | jq '.data.alerts[] | {name:.labels.alertname, state:.state}'
```

### Manual Operations
```bash
# Manually poll all invoices
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8089/qbo/sync/invoice/poll_all"

# Sync specific customer to QBO
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8089/qbo/sync/customer/{customer_id}"

# Check specific invoice status
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8089/qbo/sync/invoice/{proposal_id}/check"
```

### Restart Services
```bash
# Restart CRM API (fixes most issues)
cd monitoring
docker compose restart crm-api

# Restart full stack (nuclear option)
docker compose restart crm-api postgres-crm prometheus alertmanager grafana
```

### Logs
```bash
# CRM API logs (last 50 lines)
docker logs crm-api --tail 50

# Follow logs live
docker logs -f crm-api

# Filter for errors
docker logs crm-api | grep -i error | tail -20

# Filter for specific org
docker logs crm-api | grep 'org_id=1' | tail -20
```

---

## Links

- **Grafana Dashboard**: http://localhost:3000/d/peakpro_crm_kpis
- **Prometheus Alerts**: http://localhost:9099/alerts
- **Prometheus Rules**: http://localhost:9099/rules
- **Alert Configuration**: `monitoring/prometheus-alerts.yml`
- **Recording Rules**: `monitoring/prometheus-recording-rules.yml`
- **Alertmanager Config**: `monitoring/alertmanager.yml`

---

## On-Call Contacts

- **Primary**: Engineering Team (#engineering Slack)
- **Secondary**: Finance Ops (#finance-ops Slack)
- **Escalation**: CTO / VP Engineering
- **Critical Hours**: 24/7 for revenue-impacting alerts

---

## TCP Endpoint Down

**Alert**: `TcpEndpointDownFast`  
**Severity**: Critical  
**Layer**: TCP  

### Meaning
Blackbox Exporter cannot open a TCP connection to the instance for ≥2 minutes.

### Diagnostic Steps

**1. Check if service is running**
```bash
docker ps --filter "name=<service>"
# Look for status: Up X minutes (healthy)
```

**2. Check port mapping**
```bash
docker inspect <service> | jq '.[0].NetworkSettings.Ports'
# Verify correct port exposed and mapped
```

**3. Check Prometheus targets**
```bash
# Open targets UI
http://localhost:9090/targets
# Look for blackbox_tcp job, verify health=up
```

**4. Check container logs**
```bash
docker logs <service> --tail 50
# Look for bind errors, permission issues, crashes
```

### Common Fixes
- **Container stopped**: `docker start <service>`
- **Port not exposed**: Update `docker-compose.yml` with correct `ports:` mapping
- **Docker network issue**: Verify both services on same network (`aether-monitoring`)
- **Firewall blocking**: Check host firewall rules, security groups
- **Service crash loop**: Check logs, fix application errors

---

## TCP Endpoint Flapping

**Alert**: `TcpEndpointFlapping`  
**Severity**: Warning  
**Layer**: TCP  

### Meaning
Probe success state changed ≥4 times in a 10-minute window. Indicates intermittent connectivity or restart loops.

### Diagnostic Steps

**1. Check container restart count**
```bash
docker ps --filter "name=<service>"
# Look at uptime - if < 10m, recently restarted
docker inspect <service> | jq '.[0].RestartCount'
```

**2. Check resource pressure**
```bash
docker stats --no-stream
# Look for high CPU/memory on host or container
```

**3. Correlate with other alerts**
```bash
# Check if TcpLatencyHigh firing simultaneously
curl -s 'http://localhost:9090/api/v1/alerts' | jq '.data.alerts[] | select(.labels.instance=="<instance>") | {alert:.labels.alertname, state:.state}'
```

### Common Causes
- **Liveness probe too aggressive**: Container restarting due to healthcheck failures
- **Resource exhaustion**: OOM killer, CPU throttling
- **Network instability**: Intermittent connectivity, packet loss
- **Application crash loop**: Bug causing rapid restart cycles

---

## TCP Latency High

**Alert**: `TcpLatencyHigh`  
**Severity**: Warning  
**Layer**: TCP  

### Meaning
TCP connection time sustained above 250ms for 5+ minutes.

### Diagnostic Steps

**1. Check current latency**
```bash
# Query probe duration
curl -s 'http://localhost:9090/api/v1/query?query=probe_duration_seconds{job="blackbox_tcp",instance="<instance>"}' | jq '.data.result[0].value[1]'
```

**2. Check host load**
```bash
docker stats --no-stream
uptime  # Check load average
```

**3. Test direct connectivity**
```bash
# From host
time nc -zv localhost <port>

# From blackbox container
docker exec aether-blackbox time nc -zv <service> <port>
```

**4. Check network metrics**
```bash
# Network errors
docker exec <service> netstat -s | grep -i error

# TCP retransmits
docker exec <service> ss -ti | grep retrans
```

### Common Fixes
- **High CPU load**: Scale service, optimize code
- **Disk IO contention**: Check iowait, move to faster storage
- **Network saturation**: Check bandwidth, reduce traffic
- **Noisy neighbors**: Isolate services, add resource limits
- **DNS delays**: Use IP addresses, tune DNS settings

---

## Quick Reference Anchors

### tcp-endpoint-down
*Linked by:* TcpEndpointDownFast  
See section **TCP Endpoint Down** above for full checks & fixes.

### tcp-endpoint-flapping
*Linked by:* TcpEndpointFlapping  
See section **TCP Endpoint Flapping** above.

### tcp-latency-high
*Linked by:* TcpLatencyHigh  
See section **TCP Latency High** above.

### payment-rate-slo-burn-fast
*Linked by:* PaymentRateSLOBurnFast  
**What it means:** 1h burn rate > 2 for 30m — error budget is burning rapidly.  
**Checks:**  
- Grafana SLO dashboard: confirm burn_1h > 2  
- Look for spikes in `crm_invoices_generated_total` without matching `*_paid_total`  
- CRM/API logs for payment errors, retries, rate limits  
**Mitigations:**  
- Throttle risky flows, fix payment failures, re-run sync jobs prudently

### payment-rate-slo-burn-slow
*Linked by:* PaymentRateSLOBurnSlow  
**What it means:** 6h burn rate > 1 for 2h — sustained/repeat issues.  
**Checks:**  
- Grafana: burn_6h timeline  
- QBO integration health, credential validity, API limits  
**Mitigations:**  
- Roll back risky changes, stabilize pipeline, enact incident process

### error-budget-low
*Linked by:* PaymentRateErrorBudgetLow  
**What it means:** EBR < 50% — reduced margin for error.  
**Actions:** Tighten change windows, prioritize reliability.

### error-budget-critical
*Linked by:* PaymentRateErrorBudgetCritical  
**What it means:** EBR < 25% — SLO breach imminent.  
**Actions:** Declare/continue incident, pause risky deploys, focus on recovery.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-02 | Initial runbook creation for Sprint 5 finance alerts | AI Assistant |
| 2025-11-02 | Added TCP probe alert sections (TcpEndpointDownFast, TcpEndpointFlapping, TcpLatencyHigh) | AI Assistant |
| 2025-11-02 | Added quick reference anchors for Slack alert templates | AI Assistant |
| 2025-11-02 | Added SLO burn-rate and error budget threshold alert sections | AI Assistant |
