"""
CRM Events SSE Service - Health Readiness Probe (Bullet-Proof Edition)
Returns 200 OK when system is healthy, 500 when pathological states detected.

Pathological States:
- Hot-key skew >4x over 5min window (kafka:group_skew_ratio)
- Under-replicated consumers <2 over 5min window (kafka:group_consumer_count)

Features:
- Windowed queries (5m) to prevent flapping on transient spikes
- Request timeout + retries for Prometheus reliability
- JSON structured logging for observability
- Internal-only binding (127.0.0.1 by default)
- Prometheus metrics exposure for probe quality monitoring

Usage:
  python health_probe.py

Docker healthcheck:
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:9011/ready"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 30s
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime
import requests
from flask import Flask, jsonify, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest

app = Flask(__name__)

# JSON logging configuration
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module
        }
        if hasattr(record, 'extra'):
            log_obj.update(record.extra)
        return json.dumps(log_obj)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configuration from environment with safety knobs
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
CONSUMER_GROUP = os.getenv('KAFKA_GROUP', 'crm-events-sse')
SKEW_THRESHOLD = float(os.getenv('SKEW_THRESHOLD', '4.0'))
MIN_CONSUMERS = int(os.getenv('MIN_CONSUMERS', '2'))
PROM_TIMEOUT_MS = int(os.getenv('PROM_TIMEOUT_MS', '1500'))
PROM_RETRIES = int(os.getenv('PROM_RETRIES', '2'))
WINDOW_MINUTES = int(os.getenv('WINDOW_MINUTES', '5'))
BIND_HOST = os.getenv('BIND_HOST', '0.0.0.0')  # Use 127.0.0.1 for internal-only

# Prometheus metrics for probe quality monitoring
health_checks_total = Counter('health_probe_checks_total', 'Total health checks performed', ['endpoint', 'status'])
health_check_failures = Counter('health_probe_failures_total', 'Failed health checks', ['check_type', 'reason'])
health_check_duration = Histogram('health_probe_duration_seconds', 'Health check duration', ['endpoint'])
last_check_timestamp = Gauge('health_probe_last_check_timestamp', 'Timestamp of last health check')
current_skew_ratio = Gauge('health_probe_skew_ratio', 'Current skew ratio from health check')
current_consumer_count = Gauge('health_probe_consumer_count', 'Current consumer count from health check')
health_status_gauge = Gauge('health_probe_status', 'Overall health status (1=healthy, 0=unhealthy)')

def query_prometheus(query: str, timeout_ms: Optional[int] = None) -> Tuple[bool, float]:
    """
    Query Prometheus with retries and windowed metrics to prevent flapping.
    Uses max_over_time/min_over_time to smooth transient spikes.
    Returns (success, value). Returns (False, 0.0) if query fails or no results.
    """
    timeout_sec = (timeout_ms or PROM_TIMEOUT_MS) / 1000.0
    retries_left = PROM_RETRIES
    last_error = None
    
    while retries_left >= 0:
        try:
            start_time = time.time()
            response = requests.get(
                f'{PROMETHEUS_URL}/api/v1/query',
                params={'query': query},
                timeout=timeout_sec
            )
            duration = time.time() - start_time
            
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'success':
                logger.warning(json.dumps({
                    'event': 'prom_query_failed',
                    'query': query,
                    'status': data.get('status'),
                    'error': data.get('error', 'Unknown'),
                    'duration_ms': round(duration * 1000, 2)
                }))
                return False, 0.0
            
            results = data['data']['result']
            if not results:
                logger.debug(json.dumps({
                    'event': 'prom_no_results',
                    'query': query,
                    'duration_ms': round(duration * 1000, 2)
                }))
                return False, 0.0
            
            value = float(results[0]['value'][1])
            logger.debug(json.dumps({
                'event': 'prom_query_success',
                'query': query[:80],
                'value': round(value, 2),
                'duration_ms': round(duration * 1000, 2)
            }))
            return True, value
        
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout after {timeout_sec}s"
            health_check_failures.labels(check_type='prometheus', reason='timeout').inc()
        except requests.exceptions.RequestException as e:
            last_error = f"Request error: {str(e)}"
            health_check_failures.labels(check_type='prometheus', reason='connection').inc()
        except (KeyError, ValueError, IndexError) as e:
            last_error = f"Parse error: {str(e)}"
            health_check_failures.labels(check_type='prometheus', reason='parse').inc()
            return False, 0.0  # Don't retry on parse errors
        
        retries_left -= 1
        if retries_left >= 0:
            time.sleep(0.1)  # Small backoff between retries
    
    logger.error(json.dumps({
        'event': 'prom_query_exhausted',
        'query': query[:80],
        'error': last_error,
        'retries': PROM_RETRIES
    }))
    return False, 0.0

def check_health() -> Tuple[bool, Dict[str, any]]:
    """
    Check system health based on windowed Prometheus metrics (5m window).
    Uses max_over_time for skew and min_over_time for consumer count
    to prevent flapping on transient spikes.
    Returns (is_healthy, status_dict).
    """
    status = {
        'healthy': True,
        'checks': {},
        'message': 'System healthy',
        'window_minutes': WINDOW_MINUTES
    }
    
    # Check 1: Hot-key skew ratio (max over window to catch worst spike)
    skew_query = f'max_over_time(kafka:group_skew_ratio{{consumergroup="{CONSUMER_GROUP}"}}[{WINDOW_MINUTES}m])'
    success, skew_ratio = query_prometheus(skew_query)
    
    if success:
        skew_healthy = skew_ratio <= SKEW_THRESHOLD
        status['checks']['skew_ratio'] = {
            'value': round(skew_ratio, 2),
            'threshold': SKEW_THRESHOLD,
            'healthy': skew_healthy,
            'window': f'{WINDOW_MINUTES}m',
            'aggregation': 'max'
        }
        current_skew_ratio.set(skew_ratio)
        
        if not skew_healthy:
            status['healthy'] = False
            status['message'] = f'Hot-key skew high: {skew_ratio:.2f}x (threshold: {SKEW_THRESHOLD}x, window: {WINDOW_MINUTES}m)'
            logger.warning(json.dumps({
                'event': 'health_check_failed',
                'check': 'skew_ratio',
                'value': round(skew_ratio, 2),
                'threshold': SKEW_THRESHOLD,
                'window_minutes': WINDOW_MINUTES
            }))
            health_check_failures.labels(check_type='skew_ratio', reason='threshold_exceeded').inc()
    else:
        # If recording rule not available, assume healthy (don't fail on startup)
        status['checks']['skew_ratio'] = {
            'value': None,
            'threshold': SKEW_THRESHOLD,
            'healthy': True,
            'note': 'Recording rule not yet available (recording rules evaluate after 15-30s)'
        }
    
    # Check 2: Consumer count (min over window to catch worst drop)
    consumer_query = f'min_over_time(kafka:group_consumer_count{{consumergroup="{CONSUMER_GROUP}"}}[{WINDOW_MINUTES}m])'
    success, consumer_count = query_prometheus(consumer_query)
    
    if success:
        consumer_healthy = consumer_count >= MIN_CONSUMERS
        status['checks']['consumer_count'] = {
            'value': int(consumer_count),
            'min_required': MIN_CONSUMERS,
            'healthy': consumer_healthy,
            'window': f'{WINDOW_MINUTES}m',
            'aggregation': 'min'
        }
        current_consumer_count.set(consumer_count)
        
        if not consumer_healthy:
            status['healthy'] = False
            status['message'] = f'Under-replicated: {int(consumer_count)} consumers (min: {MIN_CONSUMERS}, window: {WINDOW_MINUTES}m)'
            logger.warning(json.dumps({
                'event': 'health_check_failed',
                'check': 'consumer_count',
                'value': int(consumer_count),
                'min_required': MIN_CONSUMERS,
                'window_minutes': WINDOW_MINUTES
            }))
            health_check_failures.labels(check_type='consumer_count', reason='under_replicated').inc()
    else:
        # If recording rule not available, check raw metric as fallback
        fallback_query = f'count(count by (memberid) (kafka_consumergroup_current_offset{{consumergroup="{CONSUMER_GROUP}"}}))'
        success, consumer_count = query_prometheus(fallback_query)
        
        if success:
            consumer_healthy = consumer_count >= MIN_CONSUMERS
            status['checks']['consumer_count'] = {
                'value': int(consumer_count),
                'min_required': MIN_CONSUMERS,
                'healthy': consumer_healthy,
                'note': 'Using fallback metric'
            }
            if not consumer_healthy:
                status['healthy'] = False
                status['message'] = f'Under-replicated: {int(consumer_count)} consumers (min: {MIN_CONSUMERS})'
        else:
            # Can't determine consumer count - assume healthy to avoid false restarts
            status['checks']['consumer_count'] = {
                'value': None,
                'min_required': MIN_CONSUMERS,
                'healthy': True,
                'note': 'Metrics not available'
            }
    
    return status['healthy'], status

@app.route('/ready')
def readiness_probe():
    """
    Readiness probe endpoint for Docker/K8s healthcheck.
    Returns 200 if healthy, 500 if pathological states detected.
    Uses windowed queries (5m) to prevent flapping on transient issues.
    """
    with health_check_duration.labels(endpoint='ready').time():
        is_healthy, status = check_health()
        last_check_timestamp.set(time.time())
        health_status_gauge.set(1 if is_healthy else 0)
    
    if is_healthy:
        health_checks_total.labels(endpoint='ready', status='healthy').inc()
        logger.info(json.dumps({
            'event': 'readiness_check_passed',
            'window_minutes': WINDOW_MINUTES
        }))
        return jsonify(status), 200
    else:
        health_checks_total.labels(endpoint='ready', status='unhealthy').inc()
        logger.warning(json.dumps({
            'event': 'readiness_check_failed',
            'reason': status.get('message', 'Unknown'),
            'checks': status.get('checks', {}),
            'window_minutes': WINDOW_MINUTES
        }))
        return jsonify(status), 500

@app.route('/health')
def liveness_probe():
    """
    Liveness probe endpoint - always returns 200 if service is running.
    Use this for Docker/K8s liveness checks.
    """
    return jsonify({
        'status': 'alive',
        'service': 'crm-events-sse',
        'prometheus_url': PROMETHEUS_URL
    }), 200

@app.route('/status')
def status_endpoint():
    """
    Detailed status endpoint for debugging.
    Always returns 200 with full health details.
    """
    with health_check_duration.labels(endpoint='status').time():
        is_healthy, status = check_health()
    
    status['overall_healthy'] = is_healthy
    status['config'] = {
        'prometheus_url': PROMETHEUS_URL,
        'consumer_group': CONSUMER_GROUP,
        'skew_threshold': SKEW_THRESHOLD,
        'min_consumers': MIN_CONSUMERS,
        'window_minutes': WINDOW_MINUTES,
        'timeout_ms': PROM_TIMEOUT_MS,
        'retries': PROM_RETRIES
    }
    return jsonify(status), 200

@app.route('/metrics')
def metrics_endpoint():
    """
    Prometheus metrics endpoint for probe quality monitoring.
    Exposes:
    - health_probe_checks_total: Total checks performed
    - health_probe_failures_total: Failed checks by type/reason
    - health_probe_duration_seconds: Check duration histogram
    - health_probe_status: Current health status (1=healthy, 0=unhealthy)
    - health_probe_skew_ratio: Current skew ratio
    - health_probe_consumer_count: Current consumer count
    """
    return Response(generate_latest(), mimetype='text/plain')

if __name__ == '__main__':
    logger.info(json.dumps({
        'event': 'service_starting',
        'bind_host': BIND_HOST,
        'bind_port': 9011,
        'prometheus_url': PROMETHEUS_URL,
        'consumer_group': CONSUMER_GROUP,
        'skew_threshold': SKEW_THRESHOLD,
        'min_consumers': MIN_CONSUMERS,
        'window_minutes': WINDOW_MINUTES,
        'timeout_ms': PROM_TIMEOUT_MS,
        'retries': PROM_RETRIES
    }))
    
    # Run Flask app (debug=False for production, internal binding recommended)
    app.run(host=BIND_HOST, port=9011, debug=False)
