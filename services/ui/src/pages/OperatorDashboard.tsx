import React, { useEffect, useState } from "react";

type EventStats = {
    status: string;
    total?: number;
    last_24h?: number;
    by_severity?: Record<string, number>;
};

type DeliveryStats = {
    status: string;
    total_queued: number;
    pending_now: number;
    near_failure: number;
    dedup_window_seconds?: number;
};

type DeliveryEntry = {
    id: number;
    alert_event_id: string;
    webhook_url: string;
    attempt_count: number;
    max_attempts: number;
    next_attempt_at?: string | null;
    last_error?: string | null;
    created_at: string;
    updated_at: string;
};

type AlertTemplate = {
    id: string;
    name: string;
    description?: string;
    event_type: string;
    source?: string | null;
    severity: string;
    window_seconds: number;
    threshold: number;
    target_webhook?: string;
    target_channel?: string;
    tenant_id?: string | null;
    created_at?: string;
};

type Delivery = {
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
};

const TENANTS = ["all", "tenant-qa", "tenant-premium", "tenant-acme"];

const OperatorDashboard: React.FC = () => {
    const [eventStats, setEventStats] = useState<EventStats | null>(null);
    const [deliveryStats, setDeliveryStats] = useState<DeliveryStats | null>(null);
    const [deliveries, setDeliveries] = useState<DeliveryEntry[]>([]);
    const [templates, setTemplates] = useState<AlertTemplate[]>([]);
    const [historicalDeliveries, setHistoricalDeliveries] = useState<Delivery[]>([]);
    const [tenant, setTenant] = useState<string>("all");
    const [loading, setLoading] = useState<boolean>(true);
    const [loadingTemplates, setLoadingTemplates] = useState<boolean>(false);
    const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const fetchAll = async (selectedTenant: string) => {
        try {
            setErrorMsg(null);
            setLoading(true);

            // Base URL for Command Center (adjust if needed)
            const baseUrl = "http://localhost:8010";

            // Build stats URL with optional tenant filter
            const statsUrl =
                selectedTenant === "all"
                    ? `${baseUrl}/events/stats`
                    : `${baseUrl}/events/stats?tenant_id=${encodeURIComponent(selectedTenant)}`;

            const [eventsRes, deliveriesStatsRes, deliveriesRes] = await Promise.all([
                fetch(statsUrl, { headers: { "X-User-Roles": "operator" } }),
                fetch(`${baseUrl}/alerts/deliveries/stats`, { headers: { "X-User-Roles": "operator" } }),
                fetch(`${baseUrl}/alerts/deliveries?limit=50`, { headers: { "X-User-Roles": "operator" } }),
            ]);

            if (!eventsRes.ok) {
                throw new Error(`events/stats failed: ${eventsRes.status}`);
            }
            if (!deliveriesStatsRes.ok) {
                throw new Error(`alerts/deliveries/stats failed: ${deliveriesStatsRes.status}`);
            }
            if (!deliveriesRes.ok) {
                throw new Error(`alerts/deliveries failed: ${deliveriesRes.status}`);
            }

            const eventsJson = await eventsRes.json();
            const deliveriesStatsJson = await deliveriesStatsRes.json();
            const deliveriesJson = await deliveriesRes.json();

            setEventStats(eventsJson);
            setDeliveryStats(deliveriesStatsJson);
            setDeliveries(deliveriesJson.deliveries ?? deliveriesJson ?? []);
        } catch (err: any) {
            console.error(err);
            setErrorMsg(err.message || "Failed to load operator data");
        } finally {
            setLoading(false);
        }
    };

    // Fetch templates whenever tenant changes
    const fetchTemplates = async (selectedTenant: string) => {
        try {
            setLoadingTemplates(true);
            const baseUrl = "http://localhost:8010";
            const tenantParam = selectedTenant === "all" ? "" : `?tenant_id=${encodeURIComponent(selectedTenant)}`;
            const res = await fetch(`${baseUrl}/alerts/templates${tenantParam}`, {
                headers: { "X-User-Roles": "operator" },
            });
            if (res.ok) {
                const data = await res.json();
                setTemplates(data.templates ?? []);
            }
        } catch (err) {
            console.error("Failed to load templates:", err);
        } finally {
            setLoadingTemplates(false);
        }
    };

    // Fetch delivery history
    const fetchDeliveryHistory = async (selectedTenant: string) => {
        try {
            setLoadingHistory(true);
            const baseUrl = "http://localhost:8010";
            const tenantParam = selectedTenant === "all" ? "" : `?tenant_id=${encodeURIComponent(selectedTenant)}`;
            const res = await fetch(`${baseUrl}/alerts/deliveries/history${tenantParam}`, {
                headers: { "X-User-Roles": "operator" },
            });
            if (res.ok) {
                const data = await res.json();
                setHistoricalDeliveries(data.deliveries ?? []);
            }
        } catch (err) {
            console.error("Failed to load delivery history:", err);
        } finally {
            setLoadingHistory(false);
        }
    };

    // Handle materializing template into real alert rule
    const handleMaterialize = async (tpl: AlertTemplate) => {
        try {
            const baseUrl = "http://localhost:8010";
            const body: any = {};
            if (tenant !== "all") {
                body.tenant_id = tenant;
            }

            const res = await fetch(`${baseUrl}/alerts/templates/${tpl.id}/materialize`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-User-Roles": "operator",
                },
                body: JSON.stringify(body),
            });

            if (!res.ok) {
                alert(`Failed to create alert rule: ${res.statusText}`);
                return;
            }

            const result = await res.json();
            alert(`✅ Alert rule created from template!\n\nRule ID: ${result.rule_id}\nRule Name: ${result.rule.name}`);
        } catch (err: any) {
            alert(`Failed to create alert rule: ${err.message}`);
        }
    };

    // Initial fetch + auto-refresh every 30s
    useEffect(() => {
        fetchAll(tenant);
        fetchTemplates(tenant);
        fetchDeliveryHistory(tenant);
        const id = setInterval(() => {
            fetchAll(tenant);
            fetchTemplates(tenant);
            fetchDeliveryHistory(tenant);
        }, 30000);
        return () => clearInterval(id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tenant]);

    const severityCounts = eventStats?.by_severity || {};
    const infoCount = severityCounts["info"] || 0;
    const warningCount = severityCounts["warning"] || 0;
    const errorCount = severityCounts["error"] || 0;
    const criticalCount = severityCounts["critical"] || 0;

    return (
        <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-semibold text-white">🎛️ Operator Dashboard</h1>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-400">Tenant:</span>
                    <select
                        value={tenant}
                        onChange={(e) => setTenant(e.target.value)}
                        className="border border-slate-600 bg-slate-800 text-white rounded px-3 py-1 text-sm"
                    >
                        <option value="all">All tenants (admin)</option>
                        {TENANTS.map((t) =>
                            t === "all" ? null : (
                                <option key={t} value={t}>
                                    {t}
                                </option>
                            )
                        )}
                    </select>
                </div>
            </div>

            {errorMsg ? (
                <div className="bg-red-900/30 border border-red-700 text-red-100 rounded p-3 text-sm">
                    {errorMsg} — ensure you send <code className="bg-red-950/50 px-1 rounded">X-User-Roles: operator</code> and
                    the Command Center is on v1.21.0+
                </div>
            ) : null}

            {/* Summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                    <p className="text-xs text-gray-400 uppercase tracking-wide">Events (last 24h)</p>
                    <p className="text-3xl font-bold mt-2 text-white">{eventStats?.last_24h ?? "—"}</p>
                    <p className="text-xs text-gray-500 mt-1">Total: {eventStats?.total ?? "—"}</p>
                </div>
                <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                    <p className="text-xs text-gray-400 uppercase tracking-wide">Alerts (warning+)</p>
                    <p className="text-3xl font-bold mt-2 text-yellow-400">{warningCount + errorCount + criticalCount}</p>
                    <p className="text-xs text-gray-500 mt-1">
                        W:{warningCount} E:{errorCount} C:{criticalCount}
                    </p>
                </div>
                <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                    <p className="text-xs text-gray-400 uppercase tracking-wide">Deliveries Pending</p>
                    <p className="text-3xl font-bold mt-2 text-blue-400">{deliveryStats?.pending_now ?? "—"}</p>
                    <p className="text-xs text-gray-500 mt-1">Total queued: {deliveryStats?.total_queued ?? "—"}</p>
                </div>
                <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                    <p className="text-xs text-gray-400 uppercase tracking-wide">Near Failure</p>
                    <p className="text-3xl font-bold mt-2 text-red-400">{deliveryStats?.near_failure ?? 0}</p>
                    <p className="text-xs text-gray-500 mt-1">5-attempt max watcher</p>
                </div>
            </div>

            {/* Delivery queue table */}
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-semibold text-white">📮 Alert Delivery Queue</h2>
                    <p className="text-xs text-gray-500">
                        Showing {deliveries.length} item{deliveries.length === 1 ? "" : "s"}
                    </p>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                        <thead>
                            <tr className="text-left text-gray-400 border-b border-slate-700">
                                <th className="py-2 pr-4">Webhook</th>
                                <th className="py-2 pr-4">Alert Event</th>
                                <th className="py-2 pr-4">Attempts</th>
                                <th className="py-2 pr-4">Next Attempt</th>
                                <th className="py-2 pr-4">Last Error</th>
                            </tr>
                        </thead>
                        <tbody className="text-gray-300">
                            {deliveries.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="py-4 text-gray-500 text-center">
                                        {loading ? "Loading…" : "No queued deliveries 🎉"}
                                    </td>
                                </tr>
                            ) : (
                                deliveries.map((d) => {
                                    const isNearFailure = d.attempt_count >= d.max_attempts - 1;
                                    return (
                                        <tr key={d.id} className="border-b border-slate-800/40 hover:bg-slate-800/30">
                                            <td className="py-2 pr-4 max-w-xs truncate" title={d.webhook_url}>
                                                <span className="text-blue-400">{d.webhook_url}</span>
                                            </td>
                                            <td className="py-2 pr-4 font-mono text-xs">{d.alert_event_id.slice(0, 8)}...</td>
                                            <td className="py-2 pr-4">
                                                <span className={isNearFailure ? "text-red-400 font-semibold" : ""}>
                                                    {d.attempt_count}/{d.max_attempts ?? 5}
                                                </span>
                                            </td>
                                            <td className="py-2 pr-4 text-xs">
                                                {d.next_attempt_at ? new Date(d.next_attempt_at).toLocaleString() : "—"}
                                            </td>
                                            <td className="py-2 pr-4 max-w-sm truncate text-xs text-red-300" title={d.last_error ?? ""}>
                                                {d.last_error ? d.last_error.slice(0, 80) : "—"}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Event severity breakdown */}
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                <h2 className="text-lg font-semibold mb-3 text-white">📊 Event Severity Breakdown</h2>
                <div className="flex gap-3 text-sm flex-wrap">
                    <span className="px-4 py-2 rounded bg-slate-800/60 text-gray-300 border border-slate-700">
                        info: <strong className="text-white">{infoCount}</strong>
                    </span>
                    <span className="px-4 py-2 rounded bg-yellow-900/40 text-yellow-100 border border-yellow-700/50">
                        warning: <strong className="text-yellow-200">{warningCount}</strong>
                    </span>
                    <span className="px-4 py-2 rounded bg-red-900/40 text-red-100 border border-red-700/50">
                        error: <strong className="text-red-200">{errorCount}</strong>
                    </span>
                    <span className="px-4 py-2 rounded bg-red-950/60 text-red-200 border border-red-800/50">
                        critical: <strong className="text-red-300">{criticalCount}</strong>
                    </span>
                </div>
            </div>

            {/* Alert Rule Templates */}
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h2 className="text-lg font-semibold text-white">📋 Alert Rule Templates</h2>
                        <p className="text-sm text-gray-400 mt-1">
                            Pre-built alert patterns you can materialize into real alert rules for the selected tenant.
                        </p>
                    </div>
                </div>
                {loadingTemplates ? (
                    <p className="text-gray-400 text-sm">Loading templates…</p>
                ) : templates.length === 0 ? (
                    <p className="text-gray-500 text-sm">No templates available. Default templates will be loaded on startup.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm">
                            <thead>
                                <tr className="text-left text-gray-400 border-b border-slate-700">
                                    <th className="py-2 pr-4">Name</th>
                                    <th className="py-2 pr-4">Event Type</th>
                                    <th className="py-2 pr-4">Severity</th>
                                    <th className="py-2 pr-4">Threshold</th>
                                    <th className="py-2 pr-4">Target</th>
                                    <th className="py-2 pr-4">Tenant</th>
                                    <th className="py-2 pr-4"></th>
                                </tr>
                            </thead>
                            <tbody className="text-gray-300">
                                {templates.map((tpl) => (
                                    <tr key={tpl.id} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                                        <td className="py-2 pr-4">
                                            <div className="font-medium text-white">{tpl.name}</div>
                                            {tpl.description ? (
                                                <div className="text-xs text-gray-500 mt-0.5">{tpl.description}</div>
                                            ) : null}
                                        </td>
                                        <td className="py-2 pr-4">
                                            <code className="text-xs bg-slate-800 px-2 py-1 rounded">
                                                {tpl.event_type || "any"}
                                            </code>
                                        </td>
                                        <td className="py-2 pr-4">
                                            <span
                                                className={
                                                    tpl.severity === "critical"
                                                        ? "px-2 py-1 rounded bg-red-950/60 text-red-200 text-xs border border-red-800/50"
                                                        : tpl.severity === "error"
                                                            ? "px-2 py-1 rounded bg-red-900/40 text-red-100 text-xs border border-red-700/50"
                                                            : tpl.severity === "warning"
                                                                ? "px-2 py-1 rounded bg-yellow-900/40 text-yellow-100 text-xs border border-yellow-700/50"
                                                                : "px-2 py-1 rounded bg-slate-800/60 text-gray-300 text-xs border border-slate-700"
                                                }
                                            >
                                                {tpl.severity}
                                            </span>
                                        </td>
                                        <td className="py-2 pr-4">
                                            {tpl.threshold} in {tpl.window_seconds}s
                                        </td>
                                        <td className="py-2 pr-4 text-xs">
                                            {tpl.target_webhook
                                                ? tpl.target_webhook.slice(0, 28) + "…"
                                                : tpl.target_channel
                                                    ? tpl.target_channel
                                                    : "—"}
                                        </td>
                                        <td className="py-2 pr-4 text-xs">{tpl.tenant_id ?? "any"}</td>
                                        <td className="py-2 pr-4 text-right">
                                            <button
                                                onClick={() => handleMaterialize(tpl)}
                                                className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded transition font-medium"
                                            >
                                                Create Rule
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Phase VIII M3: Delivery History Timeline */}
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-semibold text-white">📜 Recent Delivery History</h2>
                    <button
                        onClick={() => fetchDeliveryHistory(tenant)}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1.5 rounded transition font-medium"
                    >
                        🔄 Refresh
                    </button>
                </div>
                {loadingHistory ? (
                    <p className="text-gray-400 text-sm">Loading deliveries…</p>
                ) : historicalDeliveries.length === 0 ? (
                    <p className="text-gray-400 text-sm">No recent deliveries found.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm text-gray-300">
                            <thead className="text-xs uppercase text-gray-400 border-b border-slate-600">
                                <tr>
                                    <th className="py-2 pr-4">Status</th>
                                    <th className="py-2 pr-4">Event Type</th>
                                    <th className="py-2 pr-4">Target</th>
                                    <th className="py-2 pr-4">Attempts</th>
                                    <th className="py-2 pr-4">Tenant</th>
                                    <th className="py-2 pr-4">Created</th>
                                    <th className="py-2 pr-4">Error</th>
                                </tr>
                            </thead>
                            <tbody>
                                {historicalDeliveries.map((d) => {
                                    const statusBadgeClass =
                                        d.status === "delivered"
                                            ? "bg-emerald-500/20 text-emerald-100 border-emerald-700/50"
                                            : d.status === "failed"
                                                ? "bg-red-500/20 text-red-100 border-red-700/50"
                                                : d.status === "dead_letter"
                                                    ? "bg-red-950/60 text-red-200 border-red-800/50"
                                                    : "bg-slate-600/20 text-slate-100 border-slate-700";

                                    return (
                                        <tr key={d.id} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                                            <td className="py-2 pr-4">
                                                <span
                                                    className={`px-2 py-1 rounded text-xs border ${statusBadgeClass}`}
                                                >
                                                    {d.status}
                                                </span>
                                            </td>
                                            <td className="py-2 pr-4 text-xs">
                                                <div className="font-medium">{d.event_type ?? "—"}</div>
                                                {d.rule_name && (
                                                    <div className="text-gray-500">({d.rule_name})</div>
                                                )}
                                            </td>
                                            <td className="py-2 pr-4 text-xs">
                                                {d.target ? d.target.slice(0, 35) + (d.target.length > 35 ? "…" : "") : "—"}
                                            </td>
                                            <td className="py-2 pr-4 text-xs">
                                                <div>
                                                    {d.attempts ?? 0}/{d.max_attempts ?? 5}
                                                </div>
                                                {d.next_retry_at && (
                                                    <div className="text-gray-500">
                                                        Next: {new Date(d.next_retry_at).toLocaleTimeString()}
                                                    </div>
                                                )}
                                            </td>
                                            <td className="py-2 pr-4 text-xs">{d.tenant_id ?? "—"}</td>
                                            <td className="py-2 pr-4 text-xs">
                                                {d.created_at
                                                    ? new Date(d.created_at).toLocaleString()
                                                    : "—"}
                                            </td>
                                            <td className="py-2 pr-4 text-xs max-w-xs truncate" title={d.last_error ?? ""}>
                                                {d.last_error ?? "—"}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Additional info */}
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg p-4">
                <h2 className="text-lg font-semibold mb-2 text-white">ℹ️ System Info</h2>
                <div className="text-sm text-gray-400 space-y-1">
                    <p>
                        <strong className="text-gray-300">Dedup Window:</strong>{" "}
                        {deliveryStats?.dedup_window_seconds ? `${deliveryStats.dedup_window_seconds}s` : "300s"} (prevents alert
                        spam)
                    </p>
                    <p>
                        <strong className="text-gray-300">Auto-refresh:</strong> Every 30 seconds
                    </p>
                    <p>
                        <strong className="text-gray-300">Tenant Filter:</strong> {tenant === "all" ? "Admin view (all tenants)" : tenant}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default OperatorDashboard;
