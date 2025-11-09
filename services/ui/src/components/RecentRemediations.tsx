import React, { useEffect, useState } from "react";

type RemediationEvent = {
    id: number;
    ts: string;
    alertname: string;
    tenant: string;
    action: string;
    status: string;
    details: string;
};

type RemediationHistory = {
    items: RemediationEvent[];
    total: number;
};

type RecentRemediationsProps = {
    userRoles: string;
    selectedTenant?: string;
    onSelectTenant?: (tenant: string) => void;
};

export const RecentRemediations: React.FC<RecentRemediationsProps> = ({
    userRoles,
    selectedTenant: externalTenant,
    onSelectTenant,
}) => {
    const [data, setData] = useState<RemediationHistory | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedTenant, setSelectedTenant] = useState<string>(externalTenant ?? "all");
    const [selectedStatus, setSelectedStatus] = useState<string>("all");

    // Sync with external tenant prop
    useEffect(() => {
        if (externalTenant && externalTenant !== selectedTenant) {
            setSelectedTenant(externalTenant);
        }
    }, [externalTenant]);

    const fetchHistory = async () => {
        try {
            const res = await fetch("http://localhost:8010/ops/remediate/history?limit=10", {
                headers: { "X-User-Roles": userRoles }
            });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const json = await res.json();
            setData(json);
            setError(null);
        } catch (err) {
            console.error("Failed to load remediation history", err);
            setError(err instanceof Error ? err.message : "Failed to load");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
        const interval = setInterval(fetchHistory, 15000); // refresh every 15s
        return () => clearInterval(interval);
    }, [userRoles]);

    if (loading) {
        return (
            <div style={{ marginTop: "3rem" }}>
                <div style={{ padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                    <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>Loading remediation history...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ marginTop: "3rem" }}>
                <div style={{ padding: "1.5rem", background: "#fef2f2", borderRadius: "12px", border: "1px solid #fca5a5" }}>
                    <p style={{ fontSize: "0.875rem", color: "#991b1b" }}>Failed to load remediation history: {error}</p>
                </div>
            </div>
        );
    }

    // Derive unique tenants for filter dropdown
    const tenants = Array.from(
        new Set((data?.items ?? []).map((e) => e.tenant).filter(Boolean))
    );

    // Filter items based on selected filters
    const filteredItems = (data?.items ?? []).filter((e) => {
        const tenantOk = selectedTenant === "all" ? true : e.tenant === selectedTenant;
        const statusOk = selectedStatus === "all" ? true : e.status === selectedStatus;
        return tenantOk && statusOk;
    });

    // Calculate stats from filtered items
    const successCount = filteredItems.filter(e => e.status === "success").length;
    const errorCount = filteredItems.filter(e => e.status === "error").length;
    const successRate = filteredItems.length ? Math.round((successCount / filteredItems.length) * 100) : 0;

    return (
        <div style={{ marginTop: "3rem" }}>
            <div
                style={{
                    marginBottom: "1.5rem",
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "1rem",
                    alignItems: "center",
                }}
            >
                <div>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#111827", marginBottom: "0.25rem" }}>
                        🔄 Recent Remediations
                    </h2>
                    <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                        Autonomous recovery actions taken by the system
                    </p>
                </div>
                {/* filters / refresh controls still render in the events section */}
            </div>

            {/* Stats Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
                <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                    <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Total</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#111827" }}>{data?.total ?? 0}</div>
                </div>
                <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                    <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Success Rate</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: successRate >= 95 ? "#10b981" : successRate >= 80 ? "#f59e0b" : "#ef4444" }}>
                        {successRate}%
                    </div>
                </div>
                <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                    <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Successful</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#10b981" }}>{successCount}</div>
                </div>
                <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                    <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Failed</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#ef4444" }}>{errorCount}</div>
                </div>
            </div>

            {/* Events List */}
            <div style={{ padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: "1rem",
                        marginBottom: "1rem",
                        flexWrap: "wrap",
                    }}
                >
                    <h3 style={{ fontWeight: "600", color: "#374151" }}>Last 10 Events</h3>

                    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                        {/* Tenant filter */}
                        <select
                            value={selectedTenant}
                            onChange={(e) => {
                                const newTenant = e.target.value;
                                setSelectedTenant(newTenant);
                                if (onSelectTenant) {
                                    onSelectTenant(newTenant);
                                }
                            }}
                            style={{
                                border: "1px solid #d1d5db",
                                borderRadius: "6px",
                                padding: "0.35rem 0.5rem",
                                fontSize: "0.75rem",
                                color: "#374151",
                                background: "white",
                            }}
                        >
                            <option value="all">All tenants</option>
                            {tenants.map((t) => (
                                <option key={t} value={t}>
                                    {t}
                                </option>
                            ))}
                        </select>

                        {/* Status filter */}
                        <select
                            value={selectedStatus}
                            onChange={(e) => setSelectedStatus(e.target.value)}
                            style={{
                                border: "1px solid #d1d5db",
                                borderRadius: "6px",
                                padding: "0.35rem 0.5rem",
                                fontSize: "0.75rem",
                                color: "#374151",
                                background: "white",
                            }}
                        >
                            <option value="all">All statuses</option>
                            <option value="success">Success</option>
                            <option value="error">Error</option>
                        </select>

                        <button
                            onClick={fetchHistory}
                            style={{
                                padding: "0.375rem 0.75rem",
                                background: "#f3f4f6",
                                border: "1px solid #d1d5db",
                                borderRadius: "6px",
                                cursor: "pointer",
                                fontSize: "0.75rem",
                                fontWeight: "500",
                                color: "#374151",
                            }}
                        >
                            🔄 Refresh
                        </button>
                    </div>
                </div>

                {filteredItems.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        {filteredItems.map((event) => {
                            const isSuccess = event.status === "success";
                            const bgColor = isSuccess ? "#f0fdf4" : "#fef2f2";
                            const borderColor = isSuccess ? "#10b981" : "#ef4444";
                            const timestamp = new Date(event.ts);

                            return (
                                <div
                                    key={event.id}
                                    style={{
                                        padding: "1rem",
                                        background: bgColor,
                                        borderLeft: `4px solid ${borderColor}`,
                                        borderRadius: "6px",
                                    }}
                                >
                                    <div style={{ display: "flex", alignItems: "start", justifyContent: "space-between", gap: "1rem" }}>
                                        {/* Event Icon & Info */}
                                        <div style={{ display: "flex", alignItems: "start", gap: "0.75rem", flex: 1 }}>
                                            <span style={{ fontSize: "1.25rem", marginTop: "0.125rem" }}>
                                                {isSuccess ? "✅" : "❌"}
                                            </span>
                                            <div style={{ flex: 1 }}>
                                                {/* Alert Name & Action */}
                                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem", flexWrap: "wrap" }}>
                                                    <span style={{ fontWeight: "600", color: "#111827", fontSize: "0.875rem" }}>
                                                        {event.alertname}
                                                    </span>
                                                    <span
                                                        style={{
                                                            fontSize: "0.625rem",
                                                            padding: "0.125rem 0.5rem",
                                                            borderRadius: "9999px",
                                                            background: "#f3f4f6",
                                                            color: "#374151",
                                                            fontWeight: "600",
                                                            textTransform: "uppercase",
                                                        }}
                                                    >
                                                        {event.action.replace(/_/g, " ")}
                                                    </span>
                                                    {event.tenant && (
                                                        <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                                                            • {event.tenant}
                                                        </span>
                                                    )}
                                                </div>

                                                {/* Details */}
                                                <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "0.25rem" }}>
                                                    {event.details}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Timestamp */}
                                        <div style={{ fontSize: "0.75rem", color: "#9ca3af", textAlign: "right", whiteSpace: "nowrap" }}>
                                            {timestamp.toLocaleString()}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280", background: "#f9fafb", borderRadius: "8px" }}>
                        <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>✨</div>
                        <div style={{ fontWeight: "500", marginBottom: "0.25rem" }}>No remediations yet</div>
                        <div style={{ fontSize: "0.875rem" }}>Try selecting another tenant or clear filters.</div>
                    </div>
                )}
            </div>
        </div>
    );
};
