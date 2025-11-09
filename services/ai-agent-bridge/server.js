/**
 * AetherLink AI Agent Bridge
 *
 * Lightweight HTTP server that exposes Command Center data in AI-friendly format.
 * Your AI assistant can query this to get real-time operator insights.
 *
 * Usage:
 *   node server.js
 *
 * Then from your AI agent:
 *   GET http://localhost:3001/ops/snapshot
 */

const http = require('http');

const COMMAND_CENTER_BASE = process.env.COMMAND_CENTER_API || 'http://localhost:8010';
const PEAKPRO_URL = process.env.PEAKPRO_URL || 'http://localhost:8021';
const ROOFWONDER_URL = process.env.ROOFWONDER_URL || 'http://localhost:8022';
const POLICYPAL_URL = process.env.POLICYPAL_URL || 'http://localhost:8023';
const PORT = process.env.AI_BRIDGE_PORT || 3001;
const CORS_ORIGINS = process.env.CORS_ORIGINS || '*';
const MIN_SEVERITY = process.env.MIN_SEVERITY || 'info';
const DEBUG = process.env.DEBUG === 'true';

// Severity hierarchy for filtering
const SEVERITY_LEVELS = {
  info: 0,
  warning: 1,
  critical: 2,
};

/**
 * Fetch data from Command Center with proper headers
 */
async function fetchFromCommandCenter(path, roles = 'admin') {
  const url = `${COMMAND_CENTER_BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      'X-User-Roles': roles,
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch ${path}: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

/**
 * Get comprehensive ops snapshot for AI consumption
 */
async function getOpsSnapshot(minSeverity = MIN_SEVERITY) {
  try {
    if (DEBUG) {
      console.log(`[AI Bridge] Fetching snapshot with min_severity=${minSeverity}`);
    }

    const [health, anomalies, deliveries, peakpro, roofwonder, policypal] = await Promise.all([
      fetchFromCommandCenter('/health', 'admin').catch(() => ({ status: 'unknown' })),
      fetchFromCommandCenter('/anomalies/current', 'admin').catch(() => ({
        incidents: [],
        summary: { total_incidents: 0 }
      })),
      fetchFromCommandCenter('/alerts/deliveries/history?limit=20', 'operator').catch(() => ({
        items: []
      })),
      // Fetch from vertical apps (optional - they may not be running)
      fetch(`${PEAKPRO_URL}/ai/snapshot`).then(r => r.json()).catch(() => null),
      fetch(`${ROOFWONDER_URL}/ai/snapshot`).then(r => r.json()).catch(() => null),
      fetch(`${POLICYPAL_URL}/ai/snapshot`).then(r => r.json()).catch(() => null),
    ]);

    // Filter anomalies by severity
    const minLevel = SEVERITY_LEVELS[minSeverity] || 0;
    const filteredIncidents = (anomalies.incidents || []).filter(incident => {
      const incidentLevel = SEVERITY_LEVELS[incident.severity] || 0;
      return incidentLevel >= minLevel;
    });

    // Filter failed/pending deliveries that might need attention
    const problematicDeliveries = (deliveries.items || []).filter(d =>
      d.status === 'failed' || d.status === 'pending' || d.status === 'dead_letter'
    );

    // Calculate stats (after filtering)
    const criticalIncidents = filteredIncidents.filter(i => i.severity === 'critical');
    const warningIncidents = filteredIncidents.filter(i => i.severity === 'warning');

    // Build AI-friendly summary
    const summary = {
      timestamp: new Date().toISOString(),
      health: health.status || 'unknown',
      filters: {
        min_severity: minSeverity,
        total_incidents_before_filter: anomalies.incidents?.length || 0,
      },
      anomalies: {
        total: filteredIncidents.length,
        critical: criticalIncidents.length,
        warnings: warningIncidents.length,
        incidents: filteredIncidents,
      },
      deliveries: {
        total: deliveries.items?.length || 0,
        problematic: problematicDeliveries.length,
        failed: problematicDeliveries.filter(d => d.status === 'failed').length,
        pending: problematicDeliveries.filter(d => d.status === 'pending').length,
        dead_letter: problematicDeliveries.filter(d => d.status === 'dead_letter').length,
        items: problematicDeliveries.slice(0, 10), // Top 10 problematic
      },
      recommendations: generateRecommendations({ incidents: filteredIncidents, summary: anomalies.summary }, problematicDeliveries),
      // Include vertical app data if available
      apps: {
        peakpro: peakpro,
        roofwonder: roofwonder,
        policypal: policypal,
      }
    };

    if (DEBUG) {
      console.log(`[AI Bridge] Snapshot generated: ${summary.anomalies.total} incidents, ${summary.deliveries.problematic} problematic deliveries`);
    }

    return summary;
  } catch (error) {
    console.error('[AI Bridge] Error fetching ops snapshot:', error);
    throw error;
  }
}

/**
 * Generate actionable recommendations based on current state
 */
function generateRecommendations(anomalies, deliveries) {
  const recommendations = [];

  // Check anomalies
  if (anomalies.summary?.critical_incidents > 0) {
    recommendations.push({
      priority: 'high',
      category: 'anomaly',
      message: `${anomalies.summary.critical_incidents} critical anomalies detected. Investigate immediately.`,
      action: 'Review /anomalies/current endpoint for details',
    });
  }

  // Check failed deliveries
  const failedCount = deliveries.filter(d => d.status === 'failed').length;
  if (failedCount > 0) {
    recommendations.push({
      priority: 'medium',
      category: 'delivery',
      message: `${failedCount} failed deliveries found. Consider replaying.`,
      action: 'Use POST /alerts/deliveries/{id}/replay to retry',
    });
  }

  // Check dead letters
  const deadLetterCount = deliveries.filter(d => d.status === 'dead_letter').length;
  if (deadLetterCount > 0) {
    recommendations.push({
      priority: 'high',
      category: 'delivery',
      message: `${deadLetterCount} dead-lettered deliveries. Manual intervention required.`,
      action: 'Review error messages and fix root cause before replaying',
    });
  }

  if (recommendations.length === 0) {
    recommendations.push({
      priority: 'low',
      category: 'status',
      message: 'All systems operating normally.',
      action: 'No action required',
    });
  }

  return recommendations;
}

/**
 * Simple request router
 */
async function handleRequest(req, res) {
  // CORS headers (configurable for production)
  res.setHeader('Access-Control-Allow-Origin', CORS_ORIGINS);
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://localhost:${PORT}`);

  try {
    // Health check
    if (url.pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', service: 'ai-agent-bridge' }));
      return;
    }

    // Main ops snapshot endpoint
    if (url.pathname === '/ops/snapshot') {
      const minSeverity = url.searchParams.get('min_severity') || MIN_SEVERITY;
      console.log('[AI Bridge] Fetching ops snapshot...');
      const snapshot = await getOpsSnapshot(minSeverity);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(snapshot, null, 2));
      return;
    }

    // Anomalies only
    if (url.pathname === '/ops/anomalies') {
      const anomalies = await fetchFromCommandCenter('/anomalies/current', 'admin');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(anomalies, null, 2));
      return;
    }

    // Deliveries only
    if (url.pathname === '/ops/deliveries') {
      const limit = url.searchParams.get('limit') || '20';
      const deliveries = await fetchFromCommandCenter(`/alerts/deliveries/history?limit=${limit}`, 'operator');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(deliveries, null, 2));
      return;
    }

    // Replay delivery (passthrough)
    if (url.pathname.startsWith('/ops/replay/')) {
      if (req.method !== 'POST') {
        res.writeHead(405, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Method not allowed. Use POST.' }));
        return;
      }

      const deliveryId = url.pathname.split('/').pop();
      const result = await fetch(`${COMMAND_CENTER_BASE}/alerts/deliveries/${deliveryId}/replay`, {
        method: 'POST',
        headers: { 'X-User-Roles': 'admin' },
      });

      const data = await result.json();
      res.writeHead(result.ok ? 200 : result.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(data, null, 2));
      return;
    }

    // Not found
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: 'Not found',
      available_endpoints: [
        'GET /health',
        'GET /ops/snapshot',
        'GET /ops/anomalies',
        'GET /ops/deliveries?limit=20',
        'POST /ops/replay/{deliveryId}',
      ],
    }));
  } catch (error) {
    console.error('[AI Bridge] Error:', error);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: 'Internal server error',
      message: error.message,
    }));
  }
}

// Start server
const server = http.createServer(handleRequest);

server.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║  🤖 AetherLink AI Agent Bridge                             ║
║                                                            ║
║  Status: RUNNING                                           ║
║  Port: ${PORT}                                             ║
║  Command Center: ${COMMAND_CENTER_BASE}                    ║
║                                                            ║
║  Endpoints:                                                ║
║    GET  /health          - Bridge health check            ║
║    GET  /ops/snapshot    - Full ops state (AI-friendly)   ║
║    GET  /ops/anomalies   - Current anomalies only         ║
║    GET  /ops/deliveries  - Recent deliveries              ║
║    POST /ops/replay/:id  - Replay a delivery              ║
║                                                            ║
║  Test it:                                                  ║
║    curl http://localhost:${PORT}/ops/snapshot              ║
╚════════════════════════════════════════════════════════════╝
  `);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('[AI Bridge] Shutting down gracefully...');
  server.close(() => {
    console.log('[AI Bridge] Server closed');
    process.exit(0);
  });
});
