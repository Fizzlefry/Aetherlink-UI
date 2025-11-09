# Operator Insights Panel

## Purpose
Surface aggregated remediation statistics (1h / 24h), trends, and top offenders to operators inside Command Center.

## Data source
- Endpoint: `GET /ops/insights/trends`
- Backend: `services/command-center/ops_insight_analyzer.py`
- Refresh: 20 seconds (client-side polling)

## Placement
Rendered in `CommandCenter.tsx` after `RecentRemediations` to create:

1. Event-level view (what just happened)
2. Aggregate view (how we're trending)

## What it shows
- Last 1h remediations (count + success)
- Last 24h remediations (count + success)
- 24h success rate (color-coded)
- 24h trend (delta vs previous 24h)
- Top tenants, actions, alerts (24h)

## Empty state
If no data:

> No insight data yet. Trigger a remediation or run the test data generator.

## How to test
1. Run backend
2. Run `python generate_test_recovery_events.py 80`
3. Refresh UI -> values should populate

## Notes
- Uses inline styles to match mixed UI stack
- Safe to embed in other dashboards
