import React, { useEffect, useState, useMemo } from "react";

// Phase VIII M8: Time window types
type TimeWindowKey = '15m' | '1h' | '24h' | 'all';

const TIME_WINDOW_OPTIONS: { label: string; value: TimeWindowKey }[] = [
    { label: 'Last 15m', value: '15m' },
    { label: 'Last 1h', value: '1h' },
    { label: 'Last 24h', value: '24h' },
    { label: 'All', value: 'all' },
];

function getSinceDate(window: TimeWindowKey): Date | null {
    const now = new Date();
    switch (window) {
        case '15m':
            return new Date(now.getTime() - 15 * 60 * 1000);
        case '1h':
            return new Date(now.getTime() - 60 * 60 * 1000);
        case '24h':
            return new Date(now.getTime() - 24 * 60 * 60 * 1000);
        case 'all':
        default:
            return null;
    }
}

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
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [timeWindow, setTimeWindow] = useState<TimeWindowKey>("1h"); // Phase VIII M8
    const [selectedDeliveryId, setSelectedDeliveryId] = useState<string | null>(null);
    const [selectedDelivery, setSelectedDelivery] = useState<any>(null);
    const [loadingDeliveryDetail, setLoadingDeliveryDetail] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(true);
    const [loadingTemplates, setLoadingTemplates] = useState<boolean>(false);
    const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    // Phase VIII M9: Bulk replay state
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [bulkRunning, setBulkRunning] = useState<boolean>(false);
    const [bulkResults, setBulkResults] = useState<{ id: string; ok: boolean; error?: string }[] | null>(null);

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

    // Phase VIII M4: Open delivery detail drawer
    const handleOpenDelivery = async (id: string) => {
        setSelectedDeliveryId(id);
        setLoadingDeliveryDetail(true);
        try {
            const baseUrl = "http://localhost:8010";
            const res = await fetch(`${baseUrl}/alerts/deliveries/${id}`, {
                headers: { "X-User-Roles": "operator" },
            });
            if (res.ok) {
                const json = await res.json();
                setSelectedDelivery(json);
            } else {
                setSelectedDelivery({ error: "Failed to load delivery details." });
            }
        } catch (err) {
            console.error("Failed to load delivery:", err);
            setSelectedDelivery({ error: "Failed to load delivery details." });
        } finally {
            setLoadingDeliveryDetail(false);
        }
    };

    const handleCloseDelivery = () => {
        setSelectedDeliveryId(null);
        setSelectedDelivery(null);
    };

    // Phase VIII M7: Handle delivery replay
    const handleRetryDelivery = async (deliveryId: string) => {
        try {
            const baseUrl = "http://localhost:8010";
            const res = await fetch(`${baseUrl}/alerts/deliveries/${deliveryId}/replay`, {
                method: "POST",
                headers: { "X-User-Roles": "operator" },
            });

            if (res.ok) {
                const json = await res.json();
                alert(`✅ Delivery re-enqueued successfully!\nNew ID: ${json.new_id}\nOriginal ID: ${json.original_id}`);
                fetchDeliveryHistory(tenant); // Refresh history
                handleCloseDelivery(); // Close drawer
            } else {
                const error = await res.json();
                alert(`❌ Replay failed: ${error.detail || "Unknown error"}`);
            }
        } catch (err: any) {
            alert(`❌ Replay failed: ${err.message || "Network error"}`);
        }
    };

    // Phase VIII M9: Bulk replay handlers
    const toggleSelection = (id: string) => {
        setSelectedIds((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        );
    };

    const toggleSelectAll = () => {
        const allFilteredIds = filteredHistoricalDeliveries.map((d) => d.id);
        const allSelected = allFilteredIds.every((id) => selectedIds.includes(id));
        setSelectedIds(allSelected ? [] : allFilteredIds);
    };

    const handleBulkReplay = async () => {
        if (selectedIds.length === 0) return;

        const confirmed = window.confirm(
            `Replay ${selectedIds.length} selected deliveries?\n\nThis will re-enqueue them into the delivery pipeline.`
        );
        if (!confirmed) return;

        setBulkRunning(true);
        setBulkResults(null);

        const results: { id: string; ok: boolean; error?: string }[] = [];
        const baseUrl = "http://localhost:8010";

        for (const id of selectedIds) {
            try {
                const res = await fetch(`${baseUrl}/alerts/deliveries/${id}/replay`, {
                    method: "POST",
                    headers: { "X-User-Roles": "operator" },
                });

                if (res.ok) {
                    results.push({ id, ok: true });
                } else {
                    const error = await res.json();
                    results.push({ id, ok: false, error: error.detail || "Unknown error" });
                }
            } catch (err: any) {
                results.push({ id, ok: false, error: err.message || "Network error" });
            }
        }

        setBulkResults(results);
        setBulkRunning(false);
        setSelectedIds([]); // Clear selection

        // Refresh history to show new pending deliveries
        await fetchDeliveryHistory(tenant);

        // Show summary
        const succeeded = results.filter((r) => r.ok).length;
        const failed = results.filter((r) => !r.ok).length;
        alert(
            `✅ Bulk Replay Complete!\n\n` +
            `Total: ${results.length}\n` +
            `Succeeded: ${succeeded}\n` +
            `Failed: ${failed}${failed > 0 ? '\n\nCheck console for error details.' : ''}`
        );

        // Log failures to console for debugging
        if (failed > 0) {
            console.error('Bulk replay failures:', results.filter((r) => !r.ok));
        }
    };

    // Phase VIII M8: Filter deliveries by time window and status
    const filteredHistoricalDeliveries = useMemo(() => {
        const since = getSinceDate(timeWindow);

        return historicalDeliveries
            .filter((d) => {
                // Time filter
                if (!since) return true;
                if (!d.created_at) return true; // Include if no timestamp
                const createdAt = new Date(d.created_at);
                return createdAt >= since;
            })
            .filter((d) => {
                // Status filter
                if (statusFilter === "all") return true;
                return d.status === statusFilter;
            });
    }, [historicalDeliveries, timeWindow, statusFilter]);

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
                    <div className="flex items-center gap-3">
                        {/* Phase VIII M8: Time Window Selector */}
                        <select
                            value={timeWindow}
                            onChange={(e) => setTimeWindow(e.target.value as TimeWindowKey)}
                            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-slate-100 text-sm"
                        >
                            {TIME_WINDOW_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    ⏰ {opt.label}
                                </option>
                            ))}
                        </select>
                        {/* Phase VIII M6: Status Filter */}
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-slate-100 text-sm"
                        >
                            <option value="all">All Statuses</option>
                            <option value="delivered">✅ Delivered</option>
                            <option value="failed">❗ Failed</option>
                            <option value="pending">⏳ Pending</option>
                            <option value="dead_letter">🛑 Dead Letter</option>
                        </select>
                        <button
                            onClick={() => fetchDeliveryHistory(tenant)}
                            className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1.5 rounded transition font-medium"
                        >
                            🔄 Refresh
                        </button>
                    </div>
                </div>
                {loadingHistory ? (
                    <p className="text-gray-400 text-sm">Loading deliveries…</p>
                ) : filteredHistoricalDeliveries.length === 0 ? (
                    <p className="text-gray-400 text-sm">
                        {historicalDeliveries.length === 0
                            ? "No recent deliveries found."
                            : `No deliveries found for time window "${TIME_WINDOW_OPTIONS.find(o => o.value === timeWindow)?.label}" and status "${statusFilter}".`}
                    </p>
                ) : (
                    <>
                        {/* Phase VIII M9: Bulk Action Panel */}
                        {selectedIds.length > 0 && (
                            <div className="bg-blue-950/40 border border-blue-800 rounded-lg p-3 mb-3 flex items-center justify-between">
                                <div className="text-sm text-blue-100">
                                    <strong>{selectedIds.length}</strong> {selectedIds.length === 1 ? 'delivery' : 'deliveries'} selected
                                </div>
                                <button
                                    onClick={handleBulkReplay}
                                    disabled={bulkRunning}
                                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm px-4 py-2 rounded transition font-medium flex items-center gap-2"
                                >
                                    {bulkRunning ? (
                                        <>⏳ Replaying...</>
                                    ) : (
                                        <>🔄 Replay Selected</>
                                    )}
                                </button>
                            </div>
                        )}

                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm text-gray-300">
                                <thead className="text-xs uppercase text-gray-400 border-b border-slate-600">
                                    <tr>
                                        <th className="py-2 pr-2 w-8">
                                            <input
                                                type="checkbox"
                                                checked={
                                                    filteredHistoricalDeliveries.length > 0 &&
                                                    filteredHistoricalDeliveries.every((d) => selectedIds.includes(d.id))
                                                }
                                                onChange={toggleSelectAll}
                                                className="cursor-pointer"
                                            />
                                        </th>
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
                                    {filteredHistoricalDeliveries
                                        .map((d) => {
                                            const statusBadgeClass =
                                                d.status === "delivered"
                                                    ? "bg-emerald-500/20 text-emerald-100 border-emerald-700/50"
                                                    : d.status === "failed"
                                                        ? "bg-red-500/20 text-red-100 border-red-700/50"
                                                        : d.status === "dead_letter"
                                                            ? "bg-red-950/60 text-red-200 border-red-800/50"
                                                            : "bg-slate-600/20 text-slate-100 border-slate-700";

                                            return (
                                                <tr
                                                    key={d.id}
                                                    className="border-b border-slate-800/50 hover:bg-slate-800/40 transition"
                                                >
                                                    <td className="py-2 pr-2" onClick={(e) => e.stopPropagation()}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedIds.includes(d.id)}
                                                            onChange={() => toggleSelection(d.id)}
                                                            className="cursor-pointer"
                                                        />
                                                    </td>
                                                    <td className="py-2 pr-4 cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>
                                                        <span
                                                            className={`px-2 py-1 rounded text-xs border ${statusBadgeClass}`}
                                                        >
                                                            {d.status}
                                                        </span>
                                                    </td>
                                                    <td className="py-2 pr-4 text-xs cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>
                                                        <div className="font-medium">{d.event_type ?? "—"}</div>
                                                        {d.rule_name && (
                                                            <div className="text-gray-500">({d.rule_name})</div>
                                                        )}
                                                    </td>
                                                    <td className="py-2 pr-4 text-xs cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>
                                                        {d.target ? d.target.slice(0, 35) + (d.target.length > 35 ? "…" : "") : "—"}
                                                    </td>
                                                    <td className="py-2 pr-4 text-xs cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>
                                                        <div>
                                                            {d.attempts ?? 0}/{d.max_attempts ?? 5}
                                                        </div>
                                                        {d.next_retry_at && (
                                                            <div className="text-gray-500">
                                                                Next: {new Date(d.next_retry_at).toLocaleTimeString()}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td className="py-2 pr-4 text-xs cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>{d.tenant_id ?? "—"}</td>
                                                    <td className="py-2 pr-4 text-xs cursor-pointer" onClick={() => handleOpenDelivery(d.id)}>
                                                        {d.created_at
                                                            ? new Date(d.created_at).toLocaleString()
                                                            : "—"}
                                                    </td>
                                                    <td className="py-2 pr-4 text-xs max-w-xs truncate cursor-pointer" onClick={() => handleOpenDelivery(d.id)} title={d.last_error ?? ""}>
                                                        {d.last_error ?? "—"}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                </tbody>
                            </table>
                        </div>
                    </>
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

            {/* Phase VIII M4: Delivery Detail Drawer */}
            {selectedDeliveryId && (
                <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm">
                    <div className="w-full max-w-md h-full bg-slate-950 border-l border-slate-800 flex flex-col shadow-2xl">
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/60">
                            <div>
                                <h3 className="text-slate-100 font-semibold">Delivery Detail</h3>
                                <p className="text-slate-500 text-xs font-mono">ID: {selectedDeliveryId}</p>
                            </div>
                            <button
                                onClick={handleCloseDelivery}
                                className="text-slate-400 hover:text-slate-100 text-sm px-3 py-1 rounded hover:bg-slate-800/40 transition"
                            >
                                ✕ Close
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {loadingDeliveryDetail ? (
                                <p className="text-slate-400 text-sm">Loading delivery…</p>
                            ) : !selectedDelivery ? (
                                <p className="text-slate-500 text-sm">No data found.</p>
                            ) : selectedDelivery.error ? (
                                <p className="text-rose-300 text-sm">{selectedDelivery.error}</p>
                            ) : (
                                <>
                                    {/* Status Section */}
                                    <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-3 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs uppercase text-slate-500 font-semibold">Status</span>
                                            <span
                                                className={
                                                    selectedDelivery.status === "delivered"
                                                        ? "px-2 py-1 rounded bg-emerald-500/20 text-emerald-100 text-xs border border-emerald-700/50"
                                                        : selectedDelivery.status === "failed"
                                                            ? "px-2 py-1 rounded bg-red-500/20 text-red-100 text-xs border border-red-700/50"
                                                            : selectedDelivery.status === "dead_letter"
                                                                ? "px-2 py-1 rounded bg-rose-700/40 text-rose-100 text-xs border border-rose-800"
                                                                : "px-2 py-1 rounded bg-slate-700/40 text-slate-100 text-xs border border-slate-700"
                                                }
                                            >
                                                {selectedDelivery.status}
                                            </span>
                                        </div>
                                        <div className="text-sm text-slate-200">
                                            <span className="text-slate-500">Attempts:</span>{" "}
                                            {selectedDelivery.attempts ?? 0}/{selectedDelivery.max_attempts ?? 5}
                                        </div>
                                        {selectedDelivery.next_retry_at && (
                                            <div className="text-xs text-slate-400">
                                                Next retry: {new Date(selectedDelivery.next_retry_at).toLocaleString()}
                                            </div>
                                        )}
                                        {selectedDelivery.created_at && (
                                            <div className="text-xs text-slate-400">
                                                Created: {new Date(selectedDelivery.created_at).toLocaleString()}
                                            </div>
                                        )}
                                    </div>

                                    {/* Target & Tenant Section */}
                                    <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-3 space-y-2">
                                        <div>
                                            <div className="text-xs uppercase text-slate-500 font-semibold">Target</div>
                                            <div className="text-sm text-slate-200 break-all mt-1">
                                                {selectedDelivery.target ?? "—"}
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-xs uppercase text-slate-500 font-semibold">Tenant</div>
                                            <div className="text-sm text-slate-200 mt-1">
                                                {selectedDelivery.tenant_id ?? "—"}
                                            </div>
                                        </div>
                                        {selectedDelivery.rule_id && (
                                            <div>
                                                <div className="text-xs uppercase text-slate-500 font-semibold">Rule</div>
                                                <div className="text-sm text-slate-200 mt-1">
                                                    #{selectedDelivery.rule_id}
                                                    {selectedDelivery.rule_name && (
                                                        <span className="text-slate-400"> - {selectedDelivery.rule_name}</span>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                        {selectedDelivery.event_type && (
                                            <div>
                                                <div className="text-xs uppercase text-slate-500 font-semibold">Event Type</div>
                                                <div className="text-sm text-slate-200 mt-1 font-mono">
                                                    {selectedDelivery.event_type}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Error Section */}
                                    {selectedDelivery.last_error && (
                                        <div className="bg-rose-950/40 border border-rose-900 rounded-lg p-3">
                                            <div className="text-xs uppercase text-rose-200 font-semibold mb-2">Last Error</div>
                                            <pre className="text-xs text-rose-100 whitespace-pre-wrap break-all">
                                                {selectedDelivery.last_error}
                                            </pre>
                                        </div>
                                    )}

                                    {/* Phase VIII M7: Retry Delivery Button */}
                                    {selectedDelivery && selectedDelivery.status !== "delivered" && (
                                        <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-3">
                                            <button
                                                onClick={() => handleRetryDelivery(selectedDeliveryId!)}
                                                disabled={loadingDeliveryDetail}
                                                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white px-4 py-2 rounded transition font-medium flex items-center justify-center gap-2"
                                            >
                                                🔄 Retry Delivery
                                            </button>
                                            <p className="text-xs text-slate-400 mt-2 text-center">
                                                Re-enqueue this delivery for another attempt. Operators only.
                                            </p>
                                        </div>
                                    )}

                                    {/* Raw JSON Section */}
                                    <div className="bg-slate-900/40 border border-slate-800 rounded-lg p-3 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <div className="text-xs uppercase text-slate-500 font-semibold">Raw Delivery Data</div>
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard?.writeText(
                                                        JSON.stringify(selectedDelivery, null, 2)
                                                    );
                                                }}
                                                className="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 rounded hover:bg-slate-800/40 transition"
                                            >
                                                📋 Copy JSON
                                            </button>
                                        </div>
                                        <pre className="text-xs text-slate-300 whitespace-pre-wrap break-all max-h-64 overflow-y-auto bg-slate-950/60 p-2 rounded border border-slate-800">
                                            {JSON.stringify(selectedDelivery, null, 2)}
                                        </pre>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default OperatorDashboard;
