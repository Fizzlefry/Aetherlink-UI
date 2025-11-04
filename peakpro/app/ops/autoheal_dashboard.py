"""
Autoheal Ops Dashboard - FastAPI Backend
Proxy endpoints for Command Center integration
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI(title="Autoheal Ops API")

# Configuration
AUTOHEAL_URL = os.getenv("AUTOHEAL_URL", "http://localhost:9009")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")

# CORS for Command Center
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "https://command.aetherlink.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/ops/autoheal/health")
async def get_health():
    """Proxy autoheal health check"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AUTOHEAL_URL}/")
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Autoheal unavailable: {str(e)}")


@app.get("/api/ops/autoheal/audit")
async def get_audit(
    n: int = 200,
    kind: str = None,
    alertname: str = None,
    since: float = None,
    contains: str = None
):
    """Proxy filtered audit trail"""
    async with httpx.AsyncClient() as client:
        params = {"n": n}
        if kind:
            params["kind"] = kind
        if alertname:
            params["alertname"] = alertname
        if since:
            params["since"] = since
        if contains:
            params["contains"] = contains
        
        try:
            response = await client.get(f"{AUTOHEAL_URL}/audit", params=params)
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Audit endpoint unavailable: {str(e)}")


@app.get("/api/ops/autoheal/events")
async def get_events():
    """Proxy SSE event stream"""
    async def event_generator():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", f"{AUTOHEAL_URL}/events") as response:
                async for line in response.aiter_lines():
                    yield f"{line}\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/ops/autoheal/metrics")
async def get_metrics():
    """Proxy Prometheus metrics"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{AUTOHEAL_URL}/metrics")
            return response.text
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Metrics unavailable: {str(e)}")


@app.get("/ops/autoheal", response_class=HTMLResponse)
async def ops_dashboard():
    """Autoheal ops dashboard UI"""
    return HTMLResponse(content=OPS_DASHBOARD_HTML, status_code=200)


OPS_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autoheal Ops - Aetherlink Command Center</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 20px;
        }
        .header {
            background: #161b22;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 20px;
            border-left: 4px solid #58a6ff;
        }
        h1 {
            font-size: 28px;
            color: #58a6ff;
            margin-bottom: 8px;
        }
        .subtitle {
            font-size: 14px;
            color: #8b949e;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .panel {
            background: #161b22;
            border-radius: 6px;
            padding: 20px;
            border: 1px solid #30363d;
        }
        .panel h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #58a6ff;
        }
        .grafana-embed {
            width: 100%;
            height: 600px;
            border: none;
            border-radius: 4px;
        }
        .audit-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            font-family: 'Courier New', monospace;
        }
        .audit-table th {
            background: #0d1117;
            padding: 10px;
            text-align: left;
            border-bottom: 2px solid #30363d;
            color: #79c0ff;
        }
        .audit-table td {
            padding: 8px 10px;
            border-bottom: 1px solid #21262d;
        }
        .audit-table tr:hover {
            background: #0d1117;
        }
        .event-kind {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
        }
        .kind-webhook { background: #1f6feb; color: white; }
        .kind-skip { background: #db6d28; color: white; }
        .kind-dry_run { background: #8957e5; color: white; }
        .kind-ok { background: #238636; color: white; }
        .kind-fail { background: #da3633; color: white; }
        .filters {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .filters select, .filters input {
            background: #0d1117;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 14px;
        }
        .event-stream {
            height: 400px;
            overflow-y: auto;
            background: #0d1117;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        .event-item {
            padding: 8px;
            margin-bottom: 8px;
            border-left: 3px solid #30363d;
            background: #161b22;
            border-radius: 3px;
        }
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0d1117;
        }
        ::-webkit-scrollbar-thumb {
            background: #30363d;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ Autoheal Operations Dashboard</h1>
        <div class="subtitle">Real-time monitoring · Auto-remediation · Aetherlink Platform</div>
    </div>

    <div class="grid">
        <!-- Grafana Dashboard Embed -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 Grafana Metrics Dashboard</h2>
            <iframe 
                class="grafana-embed"
                src="http://localhost:3000/d/peakpro_crm_slo?orgId=1&refresh=30s&kiosk"
                frameborder="0">
            </iframe>
        </div>

        <!-- Audit Trail -->
        <div class="panel">
            <h2>📝 Audit Trail</h2>
            <div class="filters">
                <select id="kindFilter">
                    <option value="">All Kinds</option>
                    <option value="webhook_received">webhook_received</option>
                    <option value="decision_skip">decision_skip</option>
                    <option value="action_dry_run">action_dry_run</option>
                    <option value="action_ok">action_ok</option>
                    <option value="action_fail">action_fail</option>
                </select>
                <input type="text" id="alertFilter" placeholder="Filter by alert...">
                <button onclick="loadAudit()" style="background: #238636; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer;">Refresh</button>
            </div>
            <div style="height: 400px; overflow-y: auto;">
                <table class="audit-table" id="auditTable">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Kind</th>
                            <th>Alert</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody id="auditBody">
                        <tr><td colspan="4" style="text-align: center; padding: 20px; color: #8b949e;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Live Event Stream -->
        <div class="panel">
            <h2>📡 Live Event Stream</h2>
            <div class="event-stream" id="eventStream">
                <div style="color: #8b949e; text-align: center; padding: 20px;">Connecting to SSE...</div>
            </div>
        </div>
    </div>

    <script>
        // Load audit trail
        async function loadAudit() {
            const kind = document.getElementById('kindFilter').value;
            const alert = document.getElementById('alertFilter').value;
            
            let url = '/api/ops/autoheal/audit?n=50';
            if (kind) url += `&kind=${kind}`;
            if (alert) url += `&alertname=${alert}`;
            
            const response = await fetch(url);
            const data = await response.json();
            
            const tbody = document.getElementById('auditBody');
            tbody.innerHTML = data.events.map(ev => {
                const time = new Date(ev.ts * 1000).toLocaleTimeString();
                const kindClass = `kind-${ev.kind.replace('_', '')}`;
                return `
                    <tr>
                        <td>${time}</td>
                        <td><span class="event-kind ${kindClass}">${ev.kind}</span></td>
                        <td>${ev.alertname || '-'}</td>
                        <td>${ev.reason || ev.cmd || ev.alerts || '-'}</td>
                    </tr>
                `;
            }).join('');
        }

        // Connect to SSE stream
        const eventSource = new EventSource('/api/ops/autoheal/events');
        const streamDiv = document.getElementById('eventStream');
        
        eventSource.onmessage = (e) => {
            const event = JSON.parse(e.data);
            const time = new Date(event.ts * 1000).toLocaleTimeString();
            const eventHtml = `
                <div class="event-item">
                    <strong>${time}</strong> | <span class="event-kind kind-${event.kind.replace('_', '')}">${event.kind}</span>
                    ${event.alertname ? ` | ${event.alertname}` : ''}
                    ${event.reason ? ` | ${event.reason}` : ''}
                </div>
            `;
            streamDiv.insertAdjacentHTML('afterbegin', eventHtml);
            
            // Keep only last 50 events
            while (streamDiv.children.length > 50) {
                streamDiv.removeChild(streamDiv.lastChild);
            }
        };

        // Load initial audit data
        loadAudit();
        setInterval(loadAudit, 30000); // Refresh every 30s
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
