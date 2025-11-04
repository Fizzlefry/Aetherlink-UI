import React, { useEffect, useState } from "react";

type ServiceStatus = {
    status: string;
    http_status?: number;
    error?: string;
    url: string;
};

type HealthResponse = {
    status: string;
    services: Record<string, ServiceStatus>;
};

const CommandCenter: React.FC = () => {
    const [data, setData] = useState<HealthResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

    const fetchHealth = async () => {
        try {
            const res = await fetch("http://localhost:8010/ops/health");
            const json = await res.json();
            setData(json);
            setLastUpdate(new Date());
        } catch (err) {
            console.error("Failed to load ops health", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
        const interval = setInterval(fetchHealth, 15000); // refresh every 15s
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <div style={{ padding: "2rem", fontFamily: "system-ui" }}>
                <p>Loading Command Center…</p>
            </div>
        );
    }

    const statusColor = data?.status === "up" ? "#10b981" : "#f59e0b";
    const statusBg = data?.status === "up" ? "#d1fae5" : "#fef3c7";

    return (
        <div style={{ padding: "2rem", fontFamily: "system-ui", background: "#f9fafb", minHeight: "100vh" }}>
            {/* Header */}
            <div style={{ marginBottom: "2rem" }}>
                <h1 style={{ fontSize: "2rem", fontWeight: "bold", marginBottom: "0.5rem", color: "#111827" }}>
                    🎛️ AetherLink Command Center
                </h1>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div
                        style={{
                            display: "inline-block",
                            padding: "0.5rem 1rem",
                            borderRadius: "9999px",
                            background: statusBg,
                            color: statusColor,
                            fontWeight: "600",
                            fontSize: "0.875rem",
                        }}
                    >
                        Overall: {data?.status?.toUpperCase() ?? "UNKNOWN"}
                    </div>
                    {lastUpdate && (
                        <span style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                            Last updated: {lastUpdate.toLocaleTimeString()}
                        </span>
                    )}
                    <button
                        onClick={fetchHealth}
                        style={{
                            padding: "0.5rem 1rem",
                            background: "#3b82f6",
                            color: "white",
                            border: "none",
                            borderRadius: "6px",
                            cursor: "pointer",
                            fontSize: "0.875rem",
                            fontWeight: "500",
                        }}
                    >
                        🔄 Refresh
                    </button>
                </div>
            </div>

            {/* Service Grid */}
            <div
                style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                    gap: "1.5rem",
                }}
            >
                {data?.services &&
                    Object.entries(data.services).map(([name, svc]) => {
                        const isUp = svc.status === "up";
                        const cardBg = isUp ? "white" : "#fef2f2";
                        const badgeBg = isUp ? "#d1fae5" : "#fee2e2";
                        const badgeColor = isUp ? "#10b981" : "#ef4444";

                        return (
                            <div
                                key={name}
                                style={{
                                    borderRadius: "12px",
                                    border: `2px solid ${isUp ? "#e5e7eb" : "#fca5a5"}`,
                                    padding: "1.5rem",
                                    background: cardBg,
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                                }}
                            >
                                {/* Service Header */}
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                                    <h2 style={{ fontWeight: "600", fontSize: "1.125rem", textTransform: "capitalize", color: "#374151" }}>
                                        {name.replace(/_/g, " ")}
                                    </h2>
                                    <span
                                        style={{
                                            fontSize: "0.75rem",
                                            padding: "0.25rem 0.75rem",
                                            borderRadius: "9999px",
                                            background: badgeBg,
                                            color: badgeColor,
                                            fontWeight: "600",
                                            textTransform: "uppercase",
                                        }}
                                    >
                                        {svc.status}
                                    </span>
                                </div>

                                {/* Service Details */}
                                <div style={{ fontSize: "0.875rem", color: "#6b7280", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                    <div>
                                        <span style={{ fontWeight: "500", color: "#374151" }}>URL:</span>{" "}
                                        <span style={{ wordBreak: "break-all", fontSize: "0.75rem" }}>{svc.url}</span>
                                    </div>

                                    {svc.http_status && (
                                        <div>
                                            <span style={{ fontWeight: "500", color: "#374151" }}>HTTP Status:</span>{" "}
                                            <span style={{ color: svc.http_status === 200 ? "#10b981" : "#f59e0b" }}>
                                                {svc.http_status}
                                            </span>
                                        </div>
                                    )}

                                    {svc.error && (
                                        <div style={{ marginTop: "0.5rem", padding: "0.75rem", background: "#fef2f2", borderRadius: "6px" }}>
                                            <span style={{ fontWeight: "500", color: "#dc2626" }}>Error:</span>
                                            <p style={{ fontSize: "0.75rem", color: "#991b1b", marginTop: "0.25rem" }}>{svc.error}</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
            </div>

            {/* Footer Info */}
            <div style={{ marginTop: "3rem", padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                <h3 style={{ fontWeight: "600", marginBottom: "0.75rem", color: "#374151" }}>📊 About Command Center</h3>
                <p style={{ fontSize: "0.875rem", color: "#6b7280", lineHeight: "1.5" }}>
                    The Command Center provides real-time health monitoring of all AetherLink services.
                    Status updates automatically every 15 seconds. Green badges indicate healthy services,
                    while red badges show services that need attention.
                </p>
                <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "#9ca3af" }}>
                    Phase II Milestone 1 - Command Center v0.1.0
                </div>
            </div>
        </div>
    );
};

export default CommandCenter;
