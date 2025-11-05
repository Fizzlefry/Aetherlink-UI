# Phase IX: Intelligent Operations (Auto-Triage & Anomaly Detection)

**Status:** 🟡 Planning
**Started:** TBD
**Theme:** "From operator control to operator guidance"

---

## Mission Statement

Phase VIII gave operators **visibility and control** over failed deliveries. They can now:
- See failures in real-time
- Diagnose individual issues
- Replay failed deliveries (single or bulk)
- Prove their actions via audit trail

**Phase IX** elevates the platform from "ops can fix things" to **"AetherLink helps ops decide what to fix."**

The system becomes an **intelligent co-pilot**:
- Classifies failure patterns automatically
- Recommends which deliveries are safe to replay
- Detects anomalies and bursts before they become incidents
- Provides actionable insights on system health

---

## Success Criteria

### Operator Experience
- **Before IX:** "I see 200 failed deliveries. Where do I start?"
- **After IX:** "AetherLink says 150 are transient and safe to retry. The other 50 need attention."

### System Intelligence
- Triage accuracy > 85% (transient vs permanent failures)
- Anomaly detection latency < 30 seconds
- False positive rate < 5%
- Operator decision time reduced by 70%

### Technical Foundation
- Modular triage engine (extensible classification rules)
- Real-time pattern detection (sliding window analytics)
- Integration with Phase VIII audit trail
- Zero manual configuration required

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE IX: INTELLIGENT OPS                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐         ┌──────────────────┐             │
│  │  Delivery Data  │────────▶│  Auto-Triage     │             │
│  │  (Phase VIII)   │         │  Engine          │             │
│  └─────────────────┘         └────────┬─────────┘             │
│                                        │                        │
│                                        ▼                        │
│                              ┌─────────────────┐               │
│                              │  Classification  │               │
│                              │  - transient     │               │
│                              │  - permanent     │               │
│                              │  - rate-limited  │               │
│                              │  - unknown       │               │
│                              └────────┬─────────┘               │
│                                       │                         │
│         ┌─────────────────────────────┼─────────────────┐      │
│         ▼                             ▼                 ▼       │
│  ┌─────────────┐            ┌──────────────┐   ┌──────────┐   │
│  │   Replay    │            │   Anomaly    │   │ Operator │   │
│  │   Advisor   │            │   Detector   │   │ Insights │   │
│  └─────────────┘            └──────────────┘   └──────────┘   │
│         │                            │                │         │
│         └────────────────────────────┴────────────────┘         │
│                              ▼                                  │
│                    ┌──────────────────┐                         │
│                    │  Operator        │                         │
│                    │  Dashboard UI    │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Milestones

### M1: Auto-Triage Engine (v1.24.0) 🎯

**Goal:** Automatically classify delivery failures into actionable categories

**Backend:**
- New module: `services/command-center/auto_triage.py`
- Function: `classify_delivery(delivery: dict) -> TriageResult`
- Categories:
  - `transient-endpoint-down` (5xx, connection refused, timeout)
  - `permanent-4xx` (400, 401, 403, 404 from target)
  - `rate-limited` (429, rate limit headers)
  - `unknown` (unclassified errors)
- Score: confidence 0-100

**API:**
- `GET /triage/deliveries/{id}` - Get triage result for single delivery
- `POST /triage/deliveries/batch` - Batch triage (up to 100 IDs)
- Returns: `{category, score, reason, recommended_action}`

**UI:**
- Add "Triage" column to delivery history table
- Color-coded badges:
  - 🟢 Green: `transient-endpoint-down` (safe to retry)
  - 🔴 Red: `permanent-4xx` (needs investigation)
  - 🟡 Yellow: `rate-limited` (wait before retry)
  - ⚪ Gray: `unknown` (manual review)
- Tooltip: Shows reason + recommended action

**Success Metrics:**
- Triage endpoint response time < 100ms
- Classification accuracy > 80% (validated against manual labels)
- Zero false positives for "safe to retry"

**Dependencies:**
- Phase VIII M4 (delivery detail structure)
- Phase VIII M7 (replay endpoint for recommended actions)

---

### M2: Smart Replay Advisor (v1.24.1) 🧠

**Goal:** Guide operators to the deliveries most likely to succeed on replay

**Backend:**
- New module: `services/command-center/replay_advisor.py`
- Function: `get_replay_recommendations(tenant: str, time_window: str) -> ReplayAdvice`
- Logic:
  - Fetch recent failed deliveries
  - Run triage on each
  - Filter for `transient-endpoint-down` + score > 80
  - Sort by: age (oldest first), tenant, endpoint
- Return: Recommended IDs + summary stats

**API:**
- `GET /replay/recommendations?tenant={tenant}&since={timestamp}`
- Returns:
  ```json
  {
    "recommended_ids": ["id1", "id2", ...],
    "total_recommended": 150,
    "total_analyzed": 200,
    "confidence": "high",
    "reasoning": "150 deliveries are transient failures with >80% success probability"
  }
  ```

**UI:**
- New panel above delivery table: **"Smart Replay Advisor"**
- Shows:
  - "**150 deliveries** recommended for replay (75% of failures)"
  - Confidence indicator (High/Medium/Low)
  - Button: **"Replay All Recommended"** (uses M9 bulk replay)
- Collapsible: "Why these deliveries?"
  - Breakdown by category
  - Age distribution
  - Affected endpoints

**Success Metrics:**
- Replay success rate for recommended deliveries > 90%
- Operator time to decision < 10 seconds
- Replay advisor used in > 60% of bulk replay actions

**Dependencies:**
- Phase IX M1 (auto-triage engine)
- Phase VIII M9 (bulk replay functionality)

---

### M3: Anomaly & Burst Detection (v1.24.2) 🚨

**Goal:** Detect and alert on unusual delivery failure patterns before they become incidents

**Backend:**
- New module: `services/command-center/anomaly_detector.py`
- Sliding window analytics (5min, 15min, 1hr windows)
- Detection rules:
  - **Burst:** >50% increase in failures vs 1hr baseline
  - **Endpoint spike:** Single endpoint failures > 10x normal
  - **Tenant spike:** Single tenant failures > 5x normal
- Store incidents in audit trail
- Background task: Check every 30 seconds

**API:**
- `GET /anomalies/active` - Get current active incidents
- `GET /anomalies/history?since={timestamp}` - Historical incidents
- Returns:
  ```json
  {
    "incidents": [
      {
        "id": "incident-123",
        "type": "endpoint_spike",
        "severity": "warning",
        "target": "https://api.customer.com/webhook",
        "current_failures": 45,
        "baseline": 3,
        "detected_at": "2025-11-05T16:30:00Z",
        "status": "active"
      }
    ]
  }
  ```

**UI:**
- **Incident Banner** at top of Operator Dashboard (when active incidents exist)
- Shows:
  - "🚨 **Anomaly Detected:** 45 failures to api.customer.com (15x normal)"
  - Button: **"View Affected Deliveries"** (auto-filters delivery table)
  - Button: **"Mark as Known Issue"** (dismisses banner, logs to audit)
- Sticky until dismissed or resolved
- History view: Show past incidents with resolution status

**Success Metrics:**
- Detection latency < 30 seconds from anomaly start
- False positive rate < 5%
- Mean time to awareness (MTTA) reduced by 80%
- Incident banner used in > 50% of anomaly responses

**Dependencies:**
- Phase VIII M3 (event stats for baseline)
- Phase IX M1 (triage for incident enrichment)
- Phase VIII M10 (audit trail for incident logging)

---

### M4: Operator Insights Dashboard (v1.24.3) 📊

**Goal:** Provide strategic intelligence on system health and operator effectiveness

**Backend:**
- New module: `services/command-center/insights.py`
- Aggregate analytics:
  - Top failing endpoints (last 24hr, 7d, 30d)
  - Top tenants by failure count
  - Most active operators (from audit trail)
  - Replay success rate over time
  - Triage accuracy metrics
- Cache: Redis (5min TTL)

**API:**
- `GET /insights/endpoints?period={24h|7d|30d}&limit=10`
- `GET /insights/tenants?period={24h|7d|30d}&limit=10`
- `GET /insights/operators?period={24h|7d|30d}`
- `GET /insights/system-health?period={7d}`

**UI:**
- New tab: **"Insights"** in Operator Dashboard
- Sections:
  1. **System Health**
     - Total deliveries (success/failure ratio)
     - Replay success rate trend (line chart)
     - Triage accuracy (gauge)
  2. **Top Failing Endpoints**
     - Table: Endpoint, Failures, Success Rate, Trend (↑/↓/→)
     - Click to filter delivery history
  3. **Top Tenants by Failures**
     - Table: Tenant, Total Failures, Most Common Category
     - Click to switch tenant context
  4. **Operator Activity**
     - Table: Operator, Actions (replays), Success Rate
     - Time-of-day heatmap (when are operators most active?)
  5. **Recommendations**
     - "Consider rate-limiting for endpoint X (429 errors)"
     - "Tenant Y has 50% failures — investigate webhook config"

**Success Metrics:**
- Insights page viewed by > 40% of operators daily
- Actionable recommendations generated > 5 per day
- Operator satisfaction with insights > 4.5/5

**Dependencies:**
- Phase VIII M10 (operator audit trail)
- Phase IX M1 (triage categories for insights)
- Phase IX M3 (anomaly history for trends)

---

## Integration Points with Phase VIII

### Leveraging Existing Infrastructure

| Phase VIII Feature | Phase IX Usage |
|-------------------|----------------|
| M3: Event Stats | Baseline for anomaly detection |
| M4: Delivery Detail | Input data for triage engine |
| M7: Single Replay | Recommended action for transient failures |
| M8: Time Window | Filter context for replay advisor |
| M9: Bulk Replay | Execute recommended replay sets |
| M10: Audit Trail | Log triage decisions, incidents, operator insights |

### Data Flow

```
Delivery Failure (Phase VIII)
    ↓
Auto-Triage (IX-M1)
    ↓
Replay Advisor (IX-M2) → Bulk Replay (VIII-M9)
    ↓
Anomaly Detector (IX-M3) → Incident Banner → Operator Action
    ↓
Audit Trail (VIII-M10) → Insights Dashboard (IX-M4)
```

---

## Technical Design Decisions

### Triage Classification Rules

**Transient (Safe to Retry):**
- HTTP 5xx (500, 502, 503, 504)
- Connection errors (refused, timeout, DNS)
- Network errors (socket closed, reset by peer)

**Permanent (Needs Investigation):**
- HTTP 4xx (400, 401, 403, 404, 405)
- Webhook validation failures
- Schema errors

**Rate-Limited (Wait Before Retry):**
- HTTP 429
- Headers: `X-RateLimit-Remaining: 0`
- Error text contains "rate limit" or "throttle"

**Unknown:**
- Any error not matching above patterns
- Encrypted/generic error messages

### Anomaly Detection Thresholds

- **Burst:** >50% increase in 5min window vs 1hr baseline
- **Endpoint Spike:** >10x failures vs 24hr baseline
- **Tenant Spike:** >5x failures vs 24hr baseline

Thresholds configurable via `config.yaml` (future).

### Performance Considerations

- Triage runs on-demand (not stored, re-computed on each view)
- Anomaly detection runs every 30s in background
- Insights cached 5min (Redis)
- Batch triage: Max 100 deliveries per request

---

## Migration & Rollout Strategy

### Phase IX-M1 (Triage Engine)
1. Deploy backend module (no UI changes)
2. Test classification accuracy with historical data
3. Add UI column to delivery table (read-only)
4. Monitor triage endpoint performance
5. Roll out to all operators

### Phase IX-M2 (Replay Advisor)
1. Deploy advisor backend
2. Add UI panel (initially collapsed)
3. A/B test: Show to 50% of operators
4. Measure replay success rate improvement
5. Full rollout if success rate > 90%

### Phase IX-M3 (Anomaly Detection)
1. Deploy detector backend (passive mode)
2. Log incidents to audit (no UI banner)
3. Validate detection accuracy for 7 days
4. Enable incident banner for admins
5. Roll out to all operators if FP rate < 5%

### Phase IX-M4 (Insights Dashboard)
1. Deploy insights backend + cache
2. Add "Insights" tab (beta tag)
3. Gather operator feedback
4. Iterate on visualizations
5. Promote to primary navigation

---

## Testing Strategy

### Unit Tests
- `test_auto_triage.py`: Classification logic for each category
- `test_anomaly_detector.py`: Burst detection with synthetic data
- `test_replay_advisor.py`: Recommendation ranking
- `test_insights.py`: Aggregation accuracy

### Integration Tests
- End-to-end: Delivery failure → Triage → Replay → Success
- Anomaly flow: Inject burst → Detect → Display banner → Dismiss
- Insights: Generate audit data → Fetch insights → Validate aggregates

### Performance Tests
- Triage: 100 deliveries in < 1 second
- Anomaly detection: Process 1000 deliveries in < 5 seconds
- Insights cache: Cold load < 2 seconds

### Accuracy Validation
- Manual labeling: 200 deliveries (transient vs permanent)
- Compare triage output vs labels
- Threshold: >85% accuracy before production rollout

---

## Documentation Requirements

### Per Milestone
- Architecture diagram (with Phase VIII integration)
- API endpoint documentation
- UI screenshots
- Operator guide (when to trust recommendations)

### Phase IX Summary (After M4)
- Complete technical overview
- Impact metrics vs Phase VIII
- Lessons learned
- Future Phase X hooks

---

## Future Phase X Hooks

Phase IX sets the foundation for **fully autonomous operations**:

### Phase X: Self-Healing & Policy Engine
- **Auto-Replay Policies:** "Always retry transient failures after 5min"
- **Circuit Breakers:** "Pause endpoint X if failure rate > 80%"
- **Intelligent Backoff:** ML-optimized retry curves per endpoint
- **Predictive Alerts:** "Endpoint Y likely to fail in next 1hr"

Phase IX proves the intelligence layer works.
Phase X makes it autonomous.

---

## Success Metrics Recap

### Key Results (by end of Phase IX)

| Metric | Phase VIII (Baseline) | Phase IX (Target) |
|--------|----------------------|-------------------|
| Operator decision time | 5+ minutes | <30 seconds |
| Replay success rate | Unknown | >90% (for recommended) |
| False replay attempts | ~30% | <5% |
| MTTA (incident awareness) | 10+ minutes | <30 seconds |
| Operator satisfaction | 4.0/5 | 4.5+/5 |

### System Intelligence

- Triage accuracy: >85%
- Anomaly detection FP rate: <5%
- Insights actionability: >60% used weekly
- Zero manual configuration required: ✅

---

## Timeline Estimate

**Assuming Phase VIII pace:**

- **M1 (Triage Engine):** 1-2 days (backend + UI column)
- **M2 (Replay Advisor):** 1 day (logic + panel UI)
- **M3 (Anomaly Detection):** 2-3 days (detector + banner + history)
- **M4 (Insights Dashboard):** 2-3 days (analytics + visualizations)

**Total:** ~7-10 days (with QA + iteration)

---

## Risk Assessment

### Technical Risks

| Risk | Mitigation |
|------|-----------|
| Triage accuracy < 85% | Start with conservative rules; tune thresholds |
| Anomaly FP rate > 5% | Longer validation period; adjustable thresholds |
| Performance degradation | Cache insights; async anomaly detection |
| Operator distrust of AI | Show reasoning for every classification |

### Operator Experience Risks

| Risk | Mitigation |
|------|-----------|
| Banner fatigue (too many alerts) | Strict FP thresholds; dismissible banners |
| Recommendation overload | Limit to top 10 per session |
| Insights overwhelm | Progressive disclosure; focus on actionable |

---

## Phase IX Mantra

> **"Intelligence without autonomy, guidance without gatekeeping."**

AetherLink learns patterns and offers advice, but operators always have final control. Phase IX makes them **faster and smarter**, not redundant.

---

## Ready to Start

**Phase IX begins when Phase VIII is deployed and validated.**

First commit: `docs: Add Phase IX plan (auto-triage + intelligence layer)`
First code: `services/command-center/auto_triage.py` (M1 foundation)

**One milestone at a time.** 🚀

---

*Last Updated: November 5, 2025*
*Status: 🟡 Planning Phase*
*Next Action: Phase VIII validation → M1 kickoff*
