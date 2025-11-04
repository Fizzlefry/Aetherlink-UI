# ============================================================================
# OPTIONAL UPGRADES - Loki + Blackbox Exporter
# ============================================================================
# Add searchable logs (Loki) and HTTP uptime probes (Blackbox) to your stack
# ============================================================================

# OPTION 1: Loki + Promtail (Searchable Logs)
# ============================================================================
# Benefits:
# - Correlate alerts with application logs
# - Search logs by time range, severity, pod
# - Add "Recent Errors" panel to Grafana dashboard
#
# Paste this into your docker-compose.yml under 'services:':

  loki:
    image: grafana/loki:2.9.0
    container_name: aether-loki
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yml:/etc/loki/local-config.yaml
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.0
    container_name: aether-promtail
    volumes:
      - ./promtail-config.yml:/etc/promtail/config.yml
      - /var/log:/var/log
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped
    depends_on:
      - loki

# Don't forget to add 'loki-data:' to volumes section at bottom!

# ============================================================================
# Loki Config (create monitoring/loki-config.yml):
# ============================================================================

auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 3m
  chunk_retain_period: 1m

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h  # 7 days

# ============================================================================
# Promtail Config (create monitoring/promtail-config.yml):
# ============================================================================

server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker container logs
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: 'stream'

# ============================================================================
# OPTION 2: Blackbox Exporter (HTTP Uptime Probes)
# ============================================================================
# Benefits:
# - Monitor API uptime (HTTP 200 checks)
# - Track response latency percentiles
# - Alert on downtime or slow responses
#
# Paste this into your docker-compose.yml under 'services:':

  blackbox:
    image: prom/blackbox-exporter:v0.24.0
    container_name: aether-blackbox
    ports:
      - "9115:9115"
    volumes:
      - ./blackbox-config.yml:/etc/blackbox/config.yml
    command:
      - '--config.file=/etc/blackbox/config.yml'
    restart: unless-stopped

# ============================================================================
# Blackbox Config (create monitoring/blackbox-config.yml):
# ============================================================================

modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      method: GET
      preferred_ip_protocol: "ip4"

  http_post_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200]
      method: POST
      preferred_ip_protocol: "ip4"

# ============================================================================
# Prometheus Scrape Config (add to prometheus-config.yml under scrape_configs:):
# ============================================================================

  # Blackbox exporter for API uptime
  - job_name: 'blackbox-http'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - http://aether-api:8000/health        # Health endpoint
        - http://aether-api:8000/api/v1/status # Status endpoint
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox:9115

# ============================================================================
# Alert Example: API Down
# ============================================================================
# Add to prometheus-alerts.yml:

  - alert: APIDowntime
    expr: probe_success{job="blackbox-http"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "API endpoint {{ $labels.instance }} is down"
      description: "{{ $labels.instance }} has been unreachable for 2 minutes."

  - alert: APISlowResponse
    expr: probe_duration_seconds{job="blackbox-http"} > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "API endpoint {{ $labels.instance }} is slow"
      description: "{{ $labels.instance }} response time is {{ $value }}s (>2s for 5min)."

# ============================================================================
# Quick Deploy Commands
# ============================================================================

# After adding Loki + Promtail:
cd monitoring
docker compose up -d loki promtail

# Verify Loki:
curl http://localhost:3100/ready

# Add Loki datasource in Grafana:
# Configuration → Data Sources → Add → Loki
# URL: http://loki:3100

# After adding Blackbox:
docker compose up -d blackbox

# Verify Blackbox:
curl http://localhost:9115/probe?target=http://google.com&module=http_2xx

# Reload Prometheus to pick up new scrape config:
curl -X POST http://localhost:9090/-/reload

# ============================================================================
# Grafana Panel Examples
# ============================================================================

# Recent Errors (Loki panel):
# Query: {container="aether-api"} |= "ERROR"
# Type: Logs panel

# API Uptime % (Blackbox):
# Query: avg_over_time(probe_success{job="blackbox-http"}[24h]) * 100
# Type: Stat panel, Unit: percent(0-100)

# API Response Time (Blackbox):
# Query: probe_duration_seconds{job="blackbox-http"}
# Type: Gauge, Unit: seconds

# ============================================================================
# Cost Estimate
# ============================================================================

# Loki:
# - Disk: ~1-5GB per day (depends on log volume)
# - CPU: ~0.1 core
# - Memory: ~512MB

# Blackbox:
# - Disk: Negligible
# - CPU: ~0.05 core per 100 probes
# - Memory: ~64MB

# Total overhead: ~600MB RAM, 0.15 CPU, 1-5GB/day disk
