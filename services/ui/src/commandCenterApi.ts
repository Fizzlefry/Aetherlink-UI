// Command Center API client
const COMMAND_CENTER_BASE = "http://localhost:8010";

function getCommandCenterHeaders(userRoles: string = "operator") {
    return {
        "X-User-Roles": userRoles,
        "Content-Type": "application/json",
    };
}

// Types
export interface DeliveryHistoryItem {
    id: string;
    tenant_id?: string;
    rule_id?: number;
    rule_name?: string;
    event_type?: string;
    target?: string;
    status: "delivered" | "failed" | "pending" | "dead_letter";
    attempts?: number;
    max_attempts?: number;
    last_error?: string | null;
    next_retry_at?: string | null;
    created_at?: string;
    triage?: "low" | "medium" | "high" | "critical";
}

export interface DeliveryHistoryResponse {
    items: DeliveryHistoryItem[];
    total: number;
}

export interface AutohealRule {
    id: string;
    name?: string;
    enabled: boolean;
    cooldown_seconds?: number;
    match_endpoint?: string;
    last_updated?: string;
}

export interface AutohealRulesResponse {
    items: AutohealRule[];
    total: number;
}

export interface MetaResponse {
    build: string;
    uptime: string;
    endpoints: string[];
}

export interface HealthResponse {
    status: string;
    timestamp: string;
    service: string;
}

// API Functions
export async function fetchMeta(userRoles: string = "operator"): Promise<MetaResponse> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/meta`, {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Meta fetch failed: ${res.status}`);
    return res.json();
}

export async function fetchHealth(userRoles: string = "operator"): Promise<HealthResponse> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/healthz`, {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Health fetch failed: ${res.status}`);
    return res.json();
}

export async function fetchDeliveryHistory(params: {
    status?: string;
    tenant_id?: string;
    triage?: string;
    limit?: number;
    offset?: number;
} = {}, userRoles: string = "operator"): Promise<DeliveryHistoryResponse> {
    const url = new URL(`${COMMAND_CENTER_BASE}/alerts/deliveries/history`);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
            url.searchParams.set(k, String(v));
        }
    });

    const res = await fetch(url.toString(), {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Delivery history fetch failed: ${res.status}`);
    return res.json();
}

export async function replayDelivery(deliveryId: string, userRoles: string = "operator"): Promise<any> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/alerts/deliveries/${deliveryId}/replay`, {
        method: "POST",
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Replay failed: ${res.status}`);
    return res.json();
}

export async function fetchAutohealRules(params: {
    enabled?: boolean;
    limit?: number;
    offset?: number;
} = {}, userRoles: string = "admin"): Promise<AutohealRulesResponse> {
    const url = new URL(`${COMMAND_CENTER_BASE}/autoheal/rules`);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) {
            url.searchParams.set(k, String(v));
        }
    });

    const res = await fetch(url.toString(), {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Autoheal rules fetch failed: ${res.status}`);
    return res.json();
}

export async function clearEndpointCooldown(endpoint: string, userRoles: string = "admin"): Promise<any> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/autoheal/clear_endpoint_cooldown`, {
        method: "POST",
        headers: getCommandCenterHeaders(userRoles),
        body: JSON.stringify({ endpoint }),
    });
    if (!res.ok) throw new Error(`Clear cooldown failed: ${res.status}`);
    return res.json();
}

export async function fetchMetrics(userRoles: string = "operator"): Promise<string> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/metrics`, {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Metrics fetch failed: ${res.status}`);
    return res.text();
}

// Phase IX M3: Anomaly Detection Types
export interface AnomalyIncident {
    type: "spike" | "drop" | "error_rate" | "tenant_isolation";
    severity: "critical" | "warning";
    affected_tenant?: string;
    affected_endpoint?: string;
    metric_name: string;
    baseline_value: number;
    current_value: number;
    delta_percent: number;
    message?: string;
}

export interface AnomaliesResponse {
    incidents: AnomalyIncident[];
    summary: {
        total_incidents: number;
        critical_incidents: number;
        warning_incidents: number;
    };
    window_minutes: number;
    baseline_minutes: number;
    detected_at: string;
}

export interface AnomalyHistorySnapshot {
    timestamp: string;
    incident_count: number;
    critical_count: number;
    incidents: AnomalyIncident[];
}

export interface AnomalyHistoryResponse {
    snapshots: AnomalyHistorySnapshot[];
    hours_analyzed: number;
    generated_at: string;
}

// Phase IX M3: Anomaly Detection API Functions
export async function fetchCurrentAnomalies(userRoles: string = "admin"): Promise<AnomaliesResponse> {
    const res = await fetch(`${COMMAND_CENTER_BASE}/anomalies/current`, {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Anomalies fetch failed: ${res.status}`);
    return res.json();
}

export async function fetchAnomalyHistory(
    hours: number = 24,
    userRoles: string = "admin"
): Promise<AnomalyHistoryResponse> {
    const url = new URL(`${COMMAND_CENTER_BASE}/anomalies/history`);
    url.searchParams.set("hours", String(hours));

    const res = await fetch(url.toString(), {
        headers: getCommandCenterHeaders(userRoles),
    });
    if (!res.ok) throw new Error(`Anomaly history fetch failed: ${res.status}`);
    return res.json();
}