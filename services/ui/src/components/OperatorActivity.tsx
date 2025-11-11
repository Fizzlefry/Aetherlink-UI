import React, { useEffect, useState } from "react";
import { makeOperatorActivityWS } from "../lib/ws";
import { sendFrontendTelemetry } from "../lib/telemetry";

type ActivityItem = {
  path: string;
  method: string;
  status_code: number;
  ts: string;
  tenant?: string;
  actor?: string;
};

type OperatorActivityProps = {
  selectedTenant?: string;
};

export const OperatorActivity: React.FC<OperatorActivityProps> = ({
  selectedTenant,
}) => {
  const [items, setItems] = useState<ActivityItem[]>([]);

  // Phase XX M13: degradation state for operator activity WS
  const [wsStale, setWsStale] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [degradedReason, setDegradedReason] = useState<string | null>(null);
  const [lastWsUpdate, setLastWsUpdate] = useState<string | null>(null);
  const [lastRecoveredAt, setLastRecoveredAt] = useState<string | null>(null);

  // Phase XX M13: HTTP fallback for operator activity
  const fetchOperatorActivity = useCallback(async (): Promise<boolean> => {
    try {
      const params = new URLSearchParams();
      params.set("limit", "25"); // Fetch last 25 items
      if (selectedTenant && selectedTenant !== "all") {
        // Note: the backend might not support tenant filtering for audit, but we can try
      }

      const response = await fetch(`http://localhost:8010/analytics/audit?${params.toString()}`);
      if (!response.ok) {
        console.warn("[operator-activity] HTTP fallback failed:", response.status);
        return false;
      }

      const auditData = await response.json();
      // Transform audit data to ActivityItem format
      const activityItems: ActivityItem[] = auditData.map((item: any) => ({
        path: item.path || item.endpoint || "unknown",
        method: item.method || "UNKNOWN",
        status_code: item.status_code || 200,
        ts: item.ts || item.timestamp || new Date().toISOString(),
        tenant: item.tenant,
        actor: item.actor || item.user || "unknown",
      }));

      setItems(activityItems);

      // Phase XX M13: clear degraded on successful HTTP refresh
      setDegraded(false);
      setDegradedReason(null);
      setLastRecoveredAt(new Date().toISOString());

      return true;
    } catch (err) {
      console.warn("[operator-activity] HTTP fallback error:", err);
      return false;
    }
  }, [selectedTenant]);

  useEffect(() => {
    const wsConnection = makeOperatorActivityWS((msg: { type?: string; payload?: ActivityItem }) => {
      if (msg?.type === "operator_activity" && msg.payload) {
        setItems((prev) => {
          const withNew = [msg.payload!, ...prev];
          // Keep last 25 items
          return withNew.slice(0, 25);
        });

        // Phase XX M13: Track WS update timestamp
        setLastWsUpdate(new Date().toISOString());

        // Phase XX M13: WS is alive again, clear degraded
        setWsStale(false);
        setDegraded(false);
        setDegradedReason(null);
        const recoveredAt = new Date().toISOString();
        setLastRecoveredAt(recoveredAt);

        // Phase XX M13: report recovered via WS
        sendFrontendTelemetry({
          component: "OperatorActivity",
          event: "recovered",
          tenant: selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown",
        });
      }
    });

    // Phase XX M13: Send heartbeat every 15 seconds to keep connection alive
    const heartbeatInterval = setInterval(() => {
      const ws = wsConnection.getSocket();
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(
            JSON.stringify({
              type: "heartbeat",
              tenant: selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown",
            })
          );
        } catch (err) {
          console.warn("[operator-activity] heartbeat send failed", err);
        }
      }
    }, 15000); // 15 seconds

    return () => {
      clearInterval(heartbeatInterval);
      wsConnection.teardown();
    };
  }, [selectedTenant]);

  // Phase XX M13: Check for stale connection (no WS update for 35+ seconds)
  useEffect(() => {
    const checkStale = () => {
      if (!lastWsUpdate) {
        setWsStale(false);
        return;
      }

      const now = Date.now();
      const lastUpdate = new Date(lastWsUpdate).getTime();
      const ageSeconds = (now - lastUpdate) / 1000;

      // Mark stale if no update for 35+ seconds
      if (ageSeconds > 35) {
        setWsStale(true);
        // Phase XX M13: report WS stale
        sendFrontendTelemetry({
          component: "OperatorActivity",
          event: "ws_stale",
          tenant: selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown",
        });
      } else {
        setWsStale(false);
      }
    };

    // Check every 5 seconds
    const staleCheckInterval = setInterval(checkStale, 5000);
    checkStale(); // Initial check

    return () => clearInterval(staleCheckInterval);
  }, [lastWsUpdate, selectedTenant]);

  // Phase XX M13: WS degradation ladder
  useEffect(() => {
    // only act when we detect staleness
    if (!wsStale) return;

    let cancelled = false;

    (async () => {
      // 1) try HTTP refresh
      const ok = await fetchOperatorActivity();
      if (cancelled) return;

      if (!ok) {
        // 2) mark UI as degraded
        setDegraded(true);
        setDegradedReason("WebSocket stale and HTTP refresh failed");

        const tenantLabel =
          selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown";

        // M13: first, say HTTP was the thing that failed
        sendFrontendTelemetry({
          component: "OperatorActivity",
          event: "http_refresh_failed",
          tenant: tenantLabel,
        });

        // then, say we actually ended up degraded
        sendFrontendTelemetry({
          component: "OperatorActivity",
          event: "degraded",
          tenant: tenantLabel,
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [wsStale, fetchOperatorActivity, selectedTenant]);

  // Filter by tenant if selected
  const filtered = selectedTenant && selectedTenant !== "all"
    ? items.filter((i) => i.tenant === selectedTenant)
    : items;

  return (
    <div style={{ marginTop: "2rem" }}>
      <div
        style={{
          background: "white",
          border: "1px solid #e5e7eb",
          borderRadius: "12px",
          padding: "1.25rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "1rem",
          }}
        >
          <h3 style={{ fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>
            👤 Operator Activity
            {degraded ? ` (Degraded${degradedReason ? `: ${degradedReason}` : ""})` : null}
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
            {filtered.length} event{filtered.length === 1 ? "" : "s"}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
            maxHeight: "300px",
            overflowY: "auto",
          }}
        >
          {filtered.length === 0 ? (
            <div
              style={{
                padding: "2rem",
                textAlign: "center",
                color: "#9ca3af",
                fontSize: "0.75rem",
              }}
            >
              No recent operator actions
            </div>
          ) : (
            filtered.map((item, idx) => {
              const timestamp = new Date(item.ts);
              const isError = item.status_code >= 400;

              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: isError ? "#fef2f2" : "#f9fafb",
                    border: `1px solid ${isError ? "#fca5a5" : "#e5e7eb"}`,
                    borderRadius: "6px",
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.75rem",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isError ? "#fee2e2" : "#f3f4f6";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isError ? "#fef2f2" : "#f9fafb";
                  }}
                >
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    <div style={{ fontFamily: "monospace", fontSize: "0.7rem", color: "#374151" }}>
                      <span
                        style={{
                          fontWeight: 600,
                          color: item.method === "POST" ? "#3b82f6" : item.method === "DELETE" ? "#ef4444" : "#6b7280",
                        }}
                      >
                        {item.method}
                      </span>{" "}
                      {item.path}
                    </div>
                    <div style={{ fontSize: "0.65rem", color: "#9ca3af" }}>
                      {item.tenant ?? "no-tenant"} • {item.actor ?? "unknown"} •{" "}
                      {timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "4px",
                      fontWeight: 600,
                      background: isError ? "#fee2e2" : "#d1fae5",
                      color: isError ? "#991b1b" : "#065f46",
                    }}
                  >
                    {item.status_code}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
