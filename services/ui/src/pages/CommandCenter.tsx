import React, { useEffect, useState } from "react";

type ServiceStatus = {
    status: string;
    http_status?: number;
    error?: string;
    url: string;
};

type HealAttempt = {
    service: string;
    action: string;
    success: boolean;
    msg: string;
    timestamp: number;
};

type AutoHealStatus = {
    watching: string[];
    interval_seconds: number;
    last_report: {
        last_run: number | null;
        attempts: HealAttempt[];
    };
};

type AutoHealHistory = {
    history: HealAttempt[];
    total_in_history: number;
    limit: number;
};

type AutoHealStats = {
    total_attempts: number;
    successful: number;
    failed: number;
    success_rate: number;
    services: Record<string, number>;
    most_healed?: string;
};

type HealthResponse = {
    status: string;
    services: Record<string, ServiceStatus>;
};

const CommandCenter: React.FC = () => {
    const [data, setData] = useState<HealthResponse | null>(null);
    const [autoHealData, setAutoHealData] = useState<AutoHealStatus | null>(null);
    const [autoHealHistory, setAutoHealHistory] = useState<AutoHealHistory | null>(null);
    const [autoHealStats, setAutoHealStats] = useState<AutoHealStats | null>(null);
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

    const fetchAutoHeal = async () => {
        try {
            const res = await fetch("http://localhost:8012/autoheal/status");
            const json = await res.json();
            setAutoHealData(json);
        } catch (err) {
            console.error("Failed to load auto-heal status", err);
        }
    };

    const fetchAutoHealHistory = async () => {
        try {
            const res = await fetch("http://localhost:8012/autoheal/history?limit=10");
            const json = await res.json();
            setAutoHealHistory(json);
        } catch (err) {
            console.error("Failed to load auto-heal history", err);
        }
    };

    const fetchAutoHealStats = async () => {
        try {
            const res = await fetch("http://localhost:8012/autoheal/stats");
            const json = await res.json();
            setAutoHealStats(json);
        } catch (err) {
            console.error("Failed to load auto-heal stats", err);
        }
    };

    useEffect(() => {
        fetchHealth();
        fetchAutoHeal();
        fetchAutoHealHistory();
        fetchAutoHealStats();

        const healthInterval = setInterval(fetchHealth, 15000); // refresh every 15s
        const healInterval = setInterval(fetchAutoHeal, 15000);
        const historyInterval = setInterval(fetchAutoHealHistory, 15000);
        const statsInterval = setInterval(fetchAutoHealStats, 15000);

        return () => {
            clearInterval(healthInterval);
            clearInterval(healInterval);
            clearInterval(historyInterval);
            clearInterval(statsInterval);
        };
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

            {/* Auto-Heal Status & History */}
            {autoHealData && (
                <div style={{ marginTop: "3rem" }}>
                    {/* Status Header */}
                    <div style={{ marginBottom: "1.5rem" }}>
                        <h2 style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#111827", marginBottom: "0.5rem" }}>
                            🏥 Auto-Heal System
                        </h2>
                        <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                            Automated service recovery and health monitoring
                        </p>
                    </div>

                    {/* Stats Grid */}
                    {autoHealStats && (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
                            <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                                <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Total Attempts</div>
                                <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#111827" }}>{autoHealStats.total_attempts}</div>
                            </div>
                            <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                                <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Success Rate</div>
                                <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#10b981" }}>{autoHealStats.success_rate}%</div>
                            </div>
                            <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                                <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Successful</div>
                                <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#10b981" }}>{autoHealStats.successful}</div>
                            </div>
                            <div style={{ padding: "1rem", background: "white", borderRadius: "8px", border: "1px solid #e5e7eb" }}>
                                <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>Failed</div>
                                <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#ef4444" }}>{autoHealStats.failed}</div>
                            </div>
                        </div>
                    )}

                    {/* Configuration & Status */}
                    <div style={{ padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb", marginBottom: "1.5rem" }}>
                        <h3 style={{ fontWeight: "600", color: "#374151", marginBottom: "1rem" }}>Configuration</h3>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "1rem", fontSize: "0.875rem" }}>
                            <div>
                                <span style={{ fontWeight: "500", color: "#374151" }}>Monitoring:</span>{" "}
                                <span style={{ color: "#6b7280" }}>{autoHealData.watching.length} services</span>
                                <div style={{ marginTop: "0.25rem", fontSize: "0.75rem", color: "#9ca3af" }}>
                                    {autoHealData.watching.join(", ")}
                                </div>
                            </div>
                            <div>
                                <span style={{ fontWeight: "500", color: "#374151" }}>Check Interval:</span>{" "}
                                <span style={{ color: "#6b7280" }}>{autoHealData.interval_seconds}s</span>
                            </div>
                            {autoHealData.last_report.last_run && (
                                <div>
                                    <span style={{ fontWeight: "500", color: "#374151" }}>Last Check:</span>{" "}
                                    <span style={{ color: "#6b7280" }}>
                                        {new Date(autoHealData.last_report.last_run * 1000).toLocaleTimeString()}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Healing History */}
                    <div style={{ padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                            <h3 style={{ fontWeight: "600", color: "#374151" }}>Recent Healing Activity</h3>
                            {autoHealHistory && autoHealHistory.total_in_history > 0 && (
                                <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                                    Showing last {autoHealHistory.history.length} of {autoHealHistory.total_in_history}
                                </span>
                            )}
                        </div>

                        {autoHealHistory && autoHealHistory.history.length > 0 ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                {autoHealHistory.history.map((attempt, idx) => (
                                    <div
                                        key={idx}
                                        style={{
                                            padding: "1rem",
                                            background: attempt.success ? "#f0fdf4" : "#fef2f2",
                                            borderLeft: `4px solid ${attempt.success ? "#10b981" : "#ef4444"}`,
                                            borderRadius: "6px",
                                        }}
                                    >
                                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                                            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                                                <span style={{ fontSize: "1.25rem" }}>{attempt.success ? "✅" : "❌"}</span>
                                                <div>
                                                    <div style={{ fontWeight: "600", color: "#111827", fontSize: "0.875rem" }}>
                                                        {attempt.service}
                                                    </div>
                                                    <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                                                        {attempt.action} • {attempt.msg}
                                                    </div>
                                                </div>
                                            </div>
                                            <div style={{ fontSize: "0.75rem", color: "#9ca3af", textAlign: "right" }}>
                                                {new Date(attempt.timestamp * 1000).toLocaleString()}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280", background: "#f9fafb", borderRadius: "8px" }}>
                                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>✨</div>
                                <div style={{ fontWeight: "500", marginBottom: "0.25rem" }}>All Systems Healthy</div>
                                <div style={{ fontSize: "0.875rem" }}>No healing attempts needed recently</div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Footer Info */}
            <div style={{ marginTop: "3rem", padding: "1.5rem", background: "white", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                <h3 style={{ fontWeight: "600", marginBottom: "0.75rem", color: "#374151" }}>📊 About Command Center</h3>
                <p style={{ fontSize: "0.875rem", color: "#6b7280", lineHeight: "1.5" }}>
                    The Command Center provides real-time health monitoring of all AetherLink services.
                    Status updates automatically every 15 seconds. Green badges indicate healthy services,
                    while red badges show services that need attention.
                </p>
                <div style={{ marginTop: "1rem", fontSize: "0.75rem", color: "#9ca3af" }}>
                    Phase II - Command Center + AI Orchestrator + RBAC + Auto-Heal (v1.5.0)
                </div>
            </div>
        </div>
    );
};

export default CommandCenter;
