# Phase VIII M1: Operator Dashboard UI

**Date:** 2025-11-04
**Status:** ✅ Complete
**Version:** Unreleased (post v1.21.0)

## Overview

Visual console for operators to monitor the Event Control Plane's reliable alert delivery system built in Phase VII M5 (v1.21.0).

## What This Adds

### New UI Component
- **OperatorDashboard.tsx** - React component in `services/ui/src/pages/`
- **Route:** Click "📊 Operator" tab in main navigation
- **Auto-refresh:** Every 30 seconds
- **Tenant filtering:** Admin can view all tenants or filter by specific tenant

### Dashboard Sections

#### 1. Summary Cards (Top Row)
- **Events (last 24h)** - Total event volume from `/events/stats`
- **Alerts (warning+)** - Count of warning/error/critical events
- **Deliveries Pending** - Real-time queue depth from `/alerts/deliveries/stats`
- **Near Failure** - Deliveries close to max attempts (5)

#### 2. Alert Delivery Queue (Middle Section)
Table showing queued webhook deliveries:
- Webhook URL (truncated)
- Alert Event ID (first 8 chars)
- Attempt count (e.g., 2/5) - highlighted in red when near failure
- Next attempt timestamp
- Last error message (truncated, full text on hover)

#### 3. Event Severity Breakdown (Bottom Section)
Visual pills showing event counts by severity:
- **Info** (gray) - routine events
- **Warning** (yellow) - attention needed
- **Error** (red) - failures
- **Critical** (dark red) - urgent issues

#### 4. System Info (Footer)
- Dedup window setting (default 300s / 5 minutes)
- Auto-refresh status
- Current tenant filter

## API Endpoints Used

All endpoints added in Phase VII:
- `GET /events/stats` - Event volume and severity breakdown
- `GET /events/stats?tenant_id={tenant}` - Tenant-filtered stats
- `GET /alerts/deliveries/stats` - Queue health metrics
- `GET /alerts/deliveries?limit=50` - List of queued deliveries

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ React UI (localhost:5173)                               │
│   OperatorDashboard.tsx                                 │
│     ├─ Fetches from Command Center every 30s           │
│     ├─ Tenant selector (all, qa, premium, acme)        │
│     └─ Auto-refresh on interval                        │
└─────────────────────────────────────────────────────────┘
                      ↓ HTTP GET
┌─────────────────────────────────────────────────────────┐
│ Command Center (localhost:8010)                         │
│   routers/events.py, routers/alerts.py                 │
│     ├─ GET /events/stats                               │
│     ├─ GET /alerts/deliveries/stats                    │
│     └─ GET /alerts/deliveries                          │
└─────────────────────────────────────────────────────────┘
                      ↓ SQLite queries
┌─────────────────────────────────────────────────────────┐
│ SQLite Database (services/command-center/events.db)    │
│   ├─ events table                                      │
│   ├─ alert_delivery_queue table                       │
│   └─ alert_delivery_history table                     │
└─────────────────────────────────────────────────────────┘
```

## Usage

### For Operators
1. Navigate to AetherLink UI (localhost:5173)
2. Click "📊 Operator" tab in top navigation
3. View real-time queue status and event metrics
4. Use tenant selector to filter by tenant (admin only)
5. Dashboard auto-refreshes every 30 seconds

### For Developers
```bash
# Start the UI (from services/ui/)
npm run dev

# Access dashboard
open http://localhost:5173
# → Click "📊 Operator" tab
```

## What You Can See

**Healthy System:**
- Deliveries Pending: 0
- Near Failure: 0
- No queued deliveries in table

**Delivery Issues:**
- Pending count > 0 → Webhooks are retrying
- Near Failure > 0 → Some deliveries approaching max attempts
- Last Error column shows what's failing (e.g., "HTTP 503", "Timeout")

**Tenant Activity:**
- Filter by tenant to see their event volume
- Compare tenant-qa (noisy, 1-day retention) vs tenant-premium (quiet, 90-day retention)

## Visual Design

Matches existing AetherLink UI theme:
- Dark slate background (`bg-slate-900/40`)
- Blue accent for highlights (`text-blue-400`)
- Red for warnings/errors (`text-red-400`)
- Responsive grid layout
- Hover effects on table rows

## Benefits

1. **Visibility** - See what Phase VII M5 is actually doing
2. **Troubleshooting** - Identify broken webhooks immediately
3. **Tenant Insights** - Compare event volume across tenants
4. **Proactive Ops** - Catch near-failure deliveries before they hit dead letter

## Next Steps (Phase VIII M2+)

Potential enhancements:
- **M2: Alert Rule Templates** - Pre-built rules library
- **M3: Delivery History Timeline** - Per-alert delivery visualization
- **M4: Provider Metrics** - Success rates per Slack/Teams/Discord
- **M5: Smart Retry Profiles** - Adaptive backoff per provider

## Testing

```bash
# 1. Start Command Center with reliable delivery
cd deploy
docker-compose -f docker-compose.dev.yml up command-center

# 2. Start UI
cd services/ui
npm run dev

# 3. Access dashboard
open http://localhost:5173
# Click "📊 Operator" tab

# 4. Verify data loads
# Should see:
# - Event stats populated
# - Delivery queue (empty if no alerts pending)
# - Severity breakdown with counts
```

## Files Changed

- **services/ui/src/pages/OperatorDashboard.tsx** (NEW) - Dashboard component
- **services/ui/src/App.tsx** (MODIFIED) - Added "operator" tab and route

## Dependencies

No new dependencies required. Uses:
- React (existing)
- Fetch API (built-in)
- Existing Tailwind-style inline CSS

## Notes

- Requires Command Center v1.21.0+ (Phase VII M5) for delivery endpoints
- Requires `X-User-Roles: operator` header (handled by Keycloak in production)
- Auto-refresh can be paused by navigating away from tab
- Tenant list is hardcoded (can be made dynamic in future)

## Result

Operators now have a **single pane of glass** for:
- Event volume monitoring
- Alert delivery health
- Webhook retry status
- Tenant activity breakdown

The infrastructure you built in Phase VII (events, alerts, retention, tenancy, reliable delivery) is now **visible and actionable** through a clean UI. 🎛️
