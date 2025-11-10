import React, { useEffect, useState } from "react";
import { makeRemediationWS } from "../lib/ws";

type InsightPayload = {
  generated_at: string;
  summary: {
    last_1h: {
      total: number;
      success: number;
      success_rate: number;
      per_tenant?: Record<string, number>;
      per_action?: Record<string, number>;
      per_alert?: Record<string, number>;
    };
    last_24h: {
      total: number;
      success: number;
      success_rate: number;
      per_tenant?: Record<string, number>;
      per_action?: Record<string, number>;
      per_alert?: Record<string, number>;
    };
  };
  trends: {
    last_24h: {
      total_delta: number;
      success_rate_delta: number;
    };
  };
  top: {
    tenants_24h: Record<string, number>;
    actions_24h: Record<string, number>;
    alerts_24h: Record<string, number>;
  };
};

type OperatorInsightsProps = {
  userRoles: string;
  selectedTenant?: string;
  onSelectTenant?: (tenant: string) => void;
};

export const OperatorInsights: React.FC<OperatorInsightsProps> = ({
  userRoles,
  selectedTenant: externalTenant,
  onSelectTenant,
}) => {
  const [data, setData] = useState<InsightPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTenant, setSelectedTenant] = useState<string>(externalTenant ?? "all");

  // Sync with external tenant prop
  useEffect(() => {
    if (externalTenant && externalTenant !== selectedTenant) {
      setSelectedTenant(externalTenant);
    }
  }, [externalTenant]);

  const fetchInsights = async () => {
    try {
      const res = await fetch("http://localhost:8010/ops/insights/trends", {
        headers: {
          "X-User-Roles": userRoles,
        },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error("Failed to load operator insights", err);
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
    const id = setInterval(fetchInsights, 20000); // refresh every 20s
    return () => clearInterval(id);
  }, [userRoles]);

  useEffect(() => {
    const teardown = makeRemediationWS((msg: { type?: string }) => {
      if (msg?.type === "remediation_event") {
        fetchInsights();
      }
    });
    return teardown;
  }, [userRoles]);

  if (loading) {
    return (
      <div style={{ marginTop: "2rem" }}>
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1.5rem",
          }}
        >
          <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>Loading operator insights…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ marginTop: "2rem" }}>
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "12px",
            padding: "1.5rem",
          }}
        >
          <p style={{ fontSize: "0.875rem", color: "#b91c1c" }}>
            Failed to load operator insights: {error}
          </p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const last1h = data.summary.last_1h || { total: 0, success: 0, success_rate: 0 };
  const last24h = data.summary.last_24h || { total: 0, success: 0, success_rate: 0 };
  const trends = data.trends.last_24h || { total_delta: 0, success_rate_delta: 0 };

  // Show friendly empty state if no events exist
  if (last24h.total === 0 && last1h.total === 0) {
    return (
      <div style={{ marginTop: "2rem" }}>
        <div style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#111827" }}>
            📈 Operator Insights
          </h2>
        </div>
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1.5rem",
          }}
        >
          <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>
            No insight data yet. Trigger a remediation or run the test data generator.
          </p>
        </div>
      </div>
    );
  }

  const formatDelta = (v: number) => {
    if (v > 0) return `+${v.toFixed(1)}`;
    if (v < 0) return v.toFixed(1);
    return "0";
  };

  // Derive tenant names for filter
  const tenantEntries = Object.entries(data.top?.tenants_24h ?? {});
  const tenantNames = tenantEntries.map(([name]) => name);

  // Filter top tenants based on selection
  const filteredTenants =
    selectedTenant === "all"
      ? tenantEntries.slice(0, 4)
      : tenantEntries.filter(([name]) => name === selectedTenant);

  const topActions = Object.entries(data.top.actions_24h || {}).slice(0, 4);
  const topAlerts = Object.entries(data.top.alerts_24h || {}).slice(0, 4);

  const downloadFile = (filename: string, content: string, type = "text/plain") => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportInsightsJSON = () => {
    if (!data) return;
    downloadFile("operator-insights.json", JSON.stringify(data, null, 2), "application/json");
  };

  const handleExportInsightsCSV = () => {
    if (!data) return;
    const lines: string[] = [];
    lines.push("section,key,value");
    const s1 = data.summary?.last_1h;
    if (s1) {
      lines.push(`summary_last_1h,total,${s1.total ?? 0}`);
      lines.push(`summary_last_1h,success,${s1.success ?? 0}`);
      lines.push(`summary_last_1h,success_rate,${s1.success_rate ?? 0}`);
    }
    const s24 = data.summary?.last_24h;
    if (s24) {
      lines.push(`summary_last_24h,total,${s24.total ?? 0}`);
      lines.push(`summary_last_24h,success,${s24.success ?? 0}`);
      lines.push(`summary_last_24h,success_rate,${s24.success_rate ?? 0}`);
    }
    const tenants = data.top?.tenants_24h ?? {};
    Object.entries(tenants).forEach(([tenant, count]) => {
      lines.push(`top_tenants_24h,${tenant},${count}`);
    });
    const csv = lines.join("\n");
    downloadFile("operator-insights.csv", csv, "text/csv");
  };

  const grafanaBase = "http://localhost:3000/d/aetherlink-recovery";
  const grafanaUrl =
    selectedTenant && selectedTenant !== "all"
      ? `${grafanaBase}?var-tenant=${encodeURIComponent(selectedTenant)}`
      : grafanaBase;

  return (
    <div style={{ marginTop: "2rem" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "1rem",
          alignItems: "center",
          gap: "0.75rem",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#111827" }}>
            📊 Operator Insights
          </h2>
          <p style={{ fontSize: "0.875rem", color: "#6b7280" }}>
            Aggregated remediation trends and top offenders
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
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
              background: "white",
            }}
          >
            <option value="all">All tenants</option>
            {tenantNames.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button
            onClick={handleExportInsightsCSV}
            style={{
              padding: "0.35rem 0.6rem",
              background: "#fff",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "0.7rem",
              cursor: "pointer",
            }}
          >
            ⬇ CSV
          </button>
          <button
            onClick={handleExportInsightsJSON}
            style={{
              padding: "0.35rem 0.6rem",
              background: "#fff",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "0.7rem",
              cursor: "pointer",
            }}
          >
            ⬇ JSON
          </button>
          <a
            href={grafanaUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              padding: "0.35rem 0.6rem",
              background: "#fff",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              fontSize: "0.7rem",
              textDecoration: "none",
              color: "#1f2937",
            }}
          >
            📊 Grafana
          </a>
        </div>
      </div>

      {/* KPI Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        {/* 1h volume */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <p style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "#6b7280" }}>
            Last 1h Remediations
          </p>
          <p style={{ fontSize: "1.6rem", fontWeight: 700, color: "#111827" }}>{last1h.total}</p>
          <p style={{ fontSize: "0.7rem", color: "#6b7280" }}>
            {last1h.success} succeeded ({last1h.success_rate.toFixed(1)}%)
          </p>
        </div>

        {/* 24h volume */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <p style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "#6b7280" }}>
            Last 24h Remediations
          </p>
          <p style={{ fontSize: "1.6rem", fontWeight: 700, color: "#111827" }}>
            {last24h.total}
          </p>
          <p style={{ fontSize: "0.7rem", color: "#6b7280" }}>
            {last24h.success} succeeded ({last24h.success_rate.toFixed(1)}%)
          </p>
        </div>

        {/* 24h success rate */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <p style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "#6b7280" }}>
            24h Success Rate
          </p>
          <p
            style={{
              fontSize: "1.6rem",
              fontWeight: 700,
              color:
                last24h.success_rate >= 95
                  ? "#10b981"
                  : last24h.success_rate >= 80
                  ? "#f59e0b"
                  : "#ef4444",
            }}
          >
            {last24h.success_rate.toFixed(1)}%
          </p>
          <p style={{ fontSize: "0.7rem", color: "#6b7280" }}>
            Δ {formatDelta(trends.success_rate_delta)} pts vs prev 24h
          </p>
        </div>

        {/* 24h total delta */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <p style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "#6b7280" }}>
            24h Trend
          </p>
          <p
            style={{
              fontSize: "1.6rem",
              fontWeight: 700,
              color: trends.total_delta >= 0 ? "#10b981" : "#ef4444",
            }}
          >
            {trends.total_delta >= 0 ? "+" : ""}
            {trends.total_delta}
          </p>
          <p style={{ fontSize: "0.7rem", color: "#6b7280" }}>
            change in total remediations
          </p>
        </div>
      </div>

      {/* Top lists */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
          gap: "1rem",
        }}
      >
        {/* Top tenants */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: "0.75rem", color: "#374151" }}>
            Top tenants (24h)
          </p>
          {filteredTenants.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#9ca3af" }}>No tenant data</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {filteredTenants.map(([tenant, count]) => (
                <li
                  key={tenant}
                  onClick={() => {
                    if (onSelectTenant) {
                      onSelectTenant(tenant);
                    }
                  }}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    cursor: onSelectTenant ? "pointer" : "default",
                    padding: "0.25rem 0.5rem",
                    borderRadius: "4px",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    if (onSelectTenant) {
                      e.currentTarget.style.background = "#f3f4f6";
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <span style={{ fontSize: "0.75rem", color: "#374151" }}>{tenant}</span>
                  <span style={{ fontSize: "0.75rem", color: "#111827", fontWeight: 600 }}>{count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Top actions */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "#111827", marginBottom: "0.5rem" }}>
            Top Actions (24h)
          </h3>
          {topActions.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#9ca3af" }}>No action data</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {topActions.map(([action, count]) => (
                <li key={action} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.75rem", color: "#374151" }}>
                    {action.replace(/_/g, " ")}
                  </span>
                  <span style={{ fontSize: "0.75rem", color: "#111827", fontWeight: 600 }}>{count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Top alerts */}
        <div
          style={{
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
          }}
        >
          <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "#111827", marginBottom: "0.5rem" }}>
            Top Alerts (24h)
          </h3>
          {topAlerts.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#9ca3af" }}>No alert data</p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {topAlerts.map(([alert, count]) => (
                <li key={alert} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.75rem", color: "#374151" }}>{alert}</span>
                  <span style={{ fontSize: "0.75rem", color: "#111827", fontWeight: 600 }}>{count}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
