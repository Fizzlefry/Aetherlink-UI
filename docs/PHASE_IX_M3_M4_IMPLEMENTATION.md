# Phase IX M3+M4 Implementation Guide

**Created:** November 5, 2025
**Version:** v1.25.0-beta
**Status:** Ready for Integration

---

## Overview

Phase IX M3+M4 adds **Anomaly Detection** and **Operator Insights** to the AetherLink Intelligence Layer, completing the awareness → reasoning → action → analytics loop.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Intelligence Pipeline                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Delivery Stream                                             │
│       ↓                                                       │
│  M1: Auto-Triage (classify)                                  │
│       ↓                                                       │
│  M2: Smart Advisor (recommend)                               │
│       ↓                                                       │
│  M3: Anomaly Detector (alert) ← NEW                         │
│       ↓                                                       │
│  M4: Insights Dashboard (analyze) ← NEW                     │
│       ↓                                                       │
│  M9: Bulk Replay (act)                                       │
│       ↓                                                       │
│  M10: Audit Trail (track)                                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 New Files Created

### Backend Intelligence Layer

1. **`services/command-center/anomaly_detector.py`**
   - Core anomaly detection logic
   - Sliding-window analysis (5min vs 60min baseline)
   - Detects traffic spikes (>50% increase) and failure clusters (>10x baseline)
   - Per-tenant and per-endpoint granularity
   - **Performance:** O(n) scan, sub-second for typical workloads

2. **`services/command-center/routers/anomalies.py`**
   - `/anomalies/current` - Real-time anomaly detection
   - `/anomalies/history` - Historical trend analysis
   - Returns incident metadata with severity levels

3. **`services/command-center/routers/operator_insights.py`**
   - `/operator-insights/summary` - Aggregated metrics
   - `/operator-insights/trends` - Time-series data for charting
   - Top failing endpoints/tenants, triage distribution, replay success rates

---

## 🔧 Integration Steps

### Step 1: Register Routers in Main App

Edit `services/command-center/main.py`:

```python
from routers import anomalies, operator_insights

# After existing router imports
app.include_router(anomalies.router)
app.include_router(operator_insights.router)
```

### Step 2: Update Dockerfile

Already included in existing Dockerfile - `anomaly_detector.py` will be copied automatically.

### Step 3: Database Schema (Optional Enhancement)

For production, consider adding an `anomalies` table to persist incidents:

```sql
CREATE TABLE anomalies (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    severity TEXT NOT NULL,  -- 'critical' | 'warning'
    spike_detected BOOLEAN,
    failure_cluster_detected BOOLEAN,
    recent_count INT,
    baseline_count INT,
    recent_failures INT,
    baseline_failures INT,
    detected_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    acknowledged_by TEXT
);

CREATE INDEX idx_anomalies_detected ON anomalies(detected_at DESC);
CREATE INDEX idx_anomalies_tenant ON anomalies(tenant_id);
```

### Step 4: Frontend UI Updates

Add to `services/ui/src/pages/OperatorDashboard.tsx`:

#### A) Anomaly Banner (M3)

```tsx
// Add state
const [anomalies, setAnomalies] = useState<any[]>([]);

// Fetch anomalies on mount + refresh
useEffect(() => {
    const fetchAnomalies = async () => {
        const res = await fetch('http://localhost:8010/anomalies/current', {
            headers: { 'X-User-Roles': 'admin' }
        });
        if (res.ok) {
            const data = await res.json();
            setAnomalies(data.incidents || []);
        }
    };
    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 60000); // Every minute
    return () => clearInterval(interval);
}, []);

// Render banner (place at top of dashboard, before table)
{anomalies.length > 0 && (
    <div className="mb-4 p-4 rounded border-2 border-red-500 bg-red-50">
        <div className="flex items-center gap-3">
            <div className="text-2xl">🚨</div>
            <div className="flex-1">
                <div className="font-bold text-red-900">
                    {anomalies.length} Active Incident{anomalies.length > 1 ? 's' : ''}
                </div>
                <div className="text-sm text-red-800">
                    {anomalies[0].message}
                </div>
            </div>
            <button
                onClick={() => {
                    // Auto-filter table to affected deliveries
                    setSelectedTenant(anomalies[0].tenant_id);
                    setStatusFilter('failed');
                }}
                className="px-3 py-2 rounded bg-red-600 text-white hover:bg-red-700"
            >
                View Affected Deliveries →
            </button>
        </div>
    </div>
)}
```

#### B) Insights Tab (M4)

```tsx
// Add new tab state
const [activeTab, setActiveTab] = useState<'deliveries' | 'insights'>('deliveries');
const [insights, setInsights] = useState<any>(null);

// Fetch insights when tab selected
useEffect(() => {
    if (activeTab === 'insights') {
        fetch('http://localhost:8010/operator-insights/summary?hours=24', {
            headers: { 'X-User-Roles': 'admin' }
        })
        .then(res => res.json())
        .then(data => setInsights(data));
    }
}, [activeTab]);

// Tab navigation
<div className="flex gap-4 mb-4">
    <button
        className={activeTab === 'deliveries' ? 'font-bold' : ''}
        onClick={() => setActiveTab('deliveries')}
    >
        📊 Deliveries
    </button>
    <button
        className={activeTab === 'insights' ? 'font-bold' : ''}
        onClick={() => setActiveTab('insights')}
    >
        📈 Insights
    </button>
</div>

// Insights view
{activeTab === 'insights' && insights && (
    <div className="space-y-4">
        {/* Top Failing Endpoints */}
        <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3">Top Failing Endpoints</h3>
            <div className="space-y-2">
                {insights.top_failing_endpoints.map((ep: any) => (
                    <div key={ep.endpoint} className="flex justify-between items-center">
                        <span className="text-sm">{ep.endpoint}</span>
                        <span className="text-red-400">{ep.failures} failures ({ep.failure_rate}%)</span>
                    </div>
                ))}
            </div>
        </div>

        {/* Triage Distribution */}
        <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3">Triage Distribution</h3>
            <div className="space-y-2">
                <div className="flex justify-between">
                    <span>🟢 Transient</span>
                    <span>{insights.triage_distribution.transient_endpoint_down}</span>
                </div>
                <div className="flex justify-between">
                    <span>🔴 Permanent</span>
                    <span>{insights.triage_distribution.permanent_4xx}</span>
                </div>
                <div className="flex justify-between">
                    <span>🟡 Rate Limited</span>
                    <span>{insights.triage_distribution.rate_limited}</span>
                </div>
            </div>
        </div>

        {/* Replay Success Rate */}
        <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3">Replay Performance</h3>
            <div className="text-3xl font-bold text-green-400">
                {insights.replay_stats.replay_success_rate}%
            </div>
            <div className="text-sm text-gray-400">
                {insights.replay_stats.replay_successes} / {insights.replay_stats.total_replayed} replays succeeded
            </div>
        </div>
    </div>
)}
```

---

## 🚀 Deployment

### Local Development

```powershell
# Rebuild backend with new modules
cd C:\Users\jonmi\OneDrive\Documents\AetherLink
docker-compose -f deploy/docker-compose.dev.yml build command-center

# Restart service
docker-compose -f deploy/docker-compose.dev.yml up -d command-center

# Verify
curl http://localhost:8010/anomalies/current
curl http://localhost:8010/operator-insights/summary?hours=24
```

### Frontend

```powershell
# UI updates require recompile (Vite handles automatically)
cd services/ui
npm run dev
```

---

## 📊 API Reference

### M3: Anomaly Detection

#### `GET /anomalies/current`

**Auth:** Admin required

**Response:**
```json
{
  "incidents": [
    {
      "tenant_id": "tenant-acme",
      "endpoint": "https://api.customer.com/webhook",
      "severity": "critical",
      "recent_count": 120,
      "baseline_count": 10,
      "recent_failures": 115,
      "baseline_failures": 2,
      "spike_detected": true,
      "failure_cluster_detected": true,
      "spike_multiplier": 12.0,
      "failure_multiplier": 57.5,
      "message": "🚨 Failure Cluster: 115 failures to https://api.customer.com/webhook (57.5x normal) – Tenant: tenant-acme",
      "detected_at": "2025-11-05T14:30:00Z"
    }
  ],
  "summary": {
    "total_incidents": 1,
    "critical_incidents": 1,
    "warning_incidents": 0
  },
  "window_minutes": 5,
  "baseline_minutes": 60
}
```

#### `GET /anomalies/history?hours=24`

Returns historical anomaly snapshots for trend analysis.

### M4: Operator Insights

#### `GET /operator-insights/summary?hours=24`

**Auth:** Admin required

**Response:**
```json
{
  "top_failing_endpoints": [
    {
      "endpoint": "https://api.customer.com/webhook",
      "failures": 245,
      "total": 300,
      "failure_rate": 81.7
    }
  ],
  "top_failing_tenants": [
    {
      "tenant_id": "tenant-acme",
      "failures": 180,
      "total": 250,
      "failure_rate": 72.0
    }
  ],
  "triage_distribution": {
    "transient_endpoint_down": 120,
    "permanent_4xx": 50,
    "rate_limited": 30,
    "unknown": 45,
    "unclassified": 5
  },
  "delivery_stats": {
    "total": 1500,
    "delivered": 1200,
    "failed": 250,
    "pending": 40,
    "dead_letter": 10,
    "success_rate": 80.0
  },
  "replay_stats": {
    "total_replayed": 100,
    "replay_successes": 85,
    "replay_success_rate": 85.0
  },
  "triage_accuracy": {
    "transient_retry_success_rate": 78.5,
    "note": "Measures how often 'transient' failures succeed on retry"
  },
  "time_range": {
    "hours": 24,
    "start": "2025-11-04T14:30:00Z",
    "end": "2025-11-05T14:30:00Z"
  }
}
```

#### `GET /operator-insights/trends?hours=24&interval_hours=1`

Returns time-series data for charting (Recharts/Chart.js ready).

---

## ✅ Verification Checklist

- [ ] Backend compiles without errors
- [ ] `/anomalies/current` returns JSON (empty array if no anomalies)
- [ ] `/operator-insights/summary` returns metrics
- [ ] UI shows anomaly banner when incidents detected
- [ ] Insights tab renders charts and stats
- [ ] Clicking "View Affected Deliveries" filters table
- [ ] M3 integrates with M1 triage classifications
- [ ] M4 shows replay success rates from M9/M10

---

## 🏷️ Version Tags

```powershell
git tag -a v1.25.0 -m "Phase IX M3: Anomaly & Burst Detection"
git tag -a v1.25.1 -m "Phase IX M4: Operator Insights Dashboard"
```

---

## 📈 Success Metrics

**M3 Anomaly Detection:**
- Detection latency: < 100ms
- False positive rate: < 5%
- Coverage: 100% of delivery endpoints

**M4 Insights Dashboard:**
- Dashboard load time: < 500ms
- Chart render time: < 200ms
- Data freshness: Real-time (60s polling)

---

## 🔮 Next Steps (Phase X)

1. **Self-Healing Policies:** Auto-retry based on triage + anomaly data
2. **Circuit Breakers:** Auto-disable failing endpoints temporarily
3. **ML Model Integration:** Replace rule-based triage with trained classifier
4. **Predictive Alerting:** "Endpoint X will fail in 15 minutes" forecasts

---

**Phase IX M3+M4 Ready for Integration** ✅
**Target Release:** v1.25.0 (M3) + v1.25.1 (M4)
**Expected LOC:** ~600 lines (backend + frontend)
