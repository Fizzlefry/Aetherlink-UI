# Command Center Observability

This directory contains monitoring and visualization assets for the AetherLink Command Center.

## 📊 Grafana Dashboard

**File:** `grafana/command-center-dashboard.json`

### Dashboard Panels

1. **Service Health** - Current health status (1=healthy, 0=unhealthy)
2. **Uptime (hours)** - How long the service has been running
3. **Total Events** - Cumulative count of all events published
4. **API Requests (5m)** - Request rate over the last 5 minutes
5. **Uptime Trend** - Historical uptime graph
6. **Events by Type** - Event publication rate by event type
7. **API Response Codes** - HTTP status code distribution
8. **Prometheus Scrape OK** - Whether Prometheus can successfully scrape metrics

### Importing the Dashboard

1. Open Grafana
2. Go to **Dashboards → Import**
3. Upload or paste the JSON from `command-center-dashboard.json`
4. Select your Prometheus datasource (update `PROMETHEUS_DS` if needed)

## 📈 Prometheus Configuration

**File:** `prometheus/command-center-scrape.yml`

Add this configuration to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'command-center'
    static_configs:
      - targets: ['command-center.default.svc.cluster.local:8010']
    metrics_path: /metrics
    scrape_interval: 15s
    scrape_timeout: 5s
```

### Environment-Specific Targets

- **Kubernetes:** `command-center.default.svc.cluster.local:8010`
- **Docker Compose:** `host.docker.internal:8010`
- **Local Development:** `localhost:8010`

## 📊 Available Metrics

The Command Center exposes these Prometheus metrics:

### Gauges
- `command_center_uptime_seconds` - Service uptime in seconds
- `command_center_health` - Health status (1=healthy, 0=unhealthy)

### Counters
- `command_center_events_total{event_type, severity}` - Total events published
- `command_center_api_requests_total{method, endpoint, status}` - Total API requests

### Example Queries

```promql
# Health status
command_center_health

# Uptime in hours
command_center_uptime_seconds / 3600

# Total events published
sum(command_center_events_total)

# API request rate
sum(rate(command_center_api_requests_total[5m]))

# Events by type
sum(rate(command_center_events_total[5m])) by (event_type)

# Response codes
sum(rate(command_center_api_requests_total[5m])) by (status)
```

## 🚀 Quick Start

1. **Deploy Prometheus** with the scrape configuration
2. **Deploy Grafana** and import the dashboard
3. **Deploy Command Center** with Helm or Docker
4. **Verify** metrics are flowing: `curl http://command-center:8010/metrics`

## 🔧 Troubleshooting

### No Metrics Appearing
- Check Prometheus targets: `up{job="command-center"}`
- Verify service is accessible: `curl http://command-center:8010/healthz`
- Check Command Center logs for errors

### Dashboard Shows "No Data"
- Confirm Prometheus datasource is correctly configured in Grafana
- Verify metric names match (case-sensitive)
- Check time range includes when metrics started being collected

### Events Not Showing
- Events are only counted when published internally by the Command Center
- Check that services are registering/unregistering or other events are occurring
- Look for event-related logs in Command Center output