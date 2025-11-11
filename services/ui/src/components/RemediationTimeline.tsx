import React, { useEffect, useState, useCallback } from "react";
import {
  AreaChart,
  Area,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";
import { makeRemediationWS } from "../lib/ws";
import { sendFrontendTelemetry } from "../lib/telemetry";

type TimelinePoint = {
  ts: string;
  count: number;
};

type AnomalyPoint = {
  ts: string;
  count: number;
  baseline: number;
  factor: number;
};

type FilterMode = "all" | "anomalies" | "quiet";

type RemediationTimelineProps = {
  selectedTenant?: string;
};

// Configuration constants
const BUCKET_MINUTES = 15; // Keep in sync with backend default

/**
 * Snap ISO timestamp to the start of its time bucket.
 * Example: "2025-01-09T11:23:45Z" with 15-min buckets → "2025-01-09T11:15:00Z"
 */
function snapToBucket(isoTs: string, bucketMinutes: number): string {
  const d = new Date(isoTs);
  d.setSeconds(0, 0);
  const minutes = d.getMinutes();
  const snappedMinutes = minutes - (minutes % bucketMinutes);
  d.setMinutes(snappedMinutes);
  return d.toISOString();
}

export const RemediationTimeline: React.FC<RemediationTimelineProps> = ({
  selectedTenant,
}) => {
  const [data, setData] = useState<TimelinePoint[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyPoint[]>([]);
  const [quiet, setQuiet] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [lastWsUpdate, setLastWsUpdate] = useState<string | null>(null);
  const [lastFullRefresh, setLastFullRefresh] = useState<string | null>(null);
  const [wsStale, setWsStale] = useState(false);

  // Phase XX M10: degradation ladder
  const [degraded, setDegraded] = useState(false);
  const [degradedReason, setDegradedReason] = useState<string | null>(null);
  const [lastRecoveredAt, setLastRecoveredAt] = useState<string | null>(null);

  const fetchTimeline = useCallback(async (): Promise<boolean> => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedTenant && selectedTenant !== "all") {
        params.set("tenant", selectedTenant);
      }
      // 24h window with 15-minute buckets
      params.set("window_minutes", "1440");
      params.set("bucket_minutes", "15");

      // Fetch both timeline data and anomalies in parallel
      const [timelineRes, anomalyRes] = await Promise.all([
        fetch(`http://localhost:8010/ops/remediations/timeline?${params.toString()}`),
        fetch(`http://localhost:8010/ops/remediations/timeline/anomalies?${params.toString()}`),
      ]);

      const timelineJson = await timelineRes.json();
      const anomalyJson = await anomalyRes.json();

      setData(timelineJson.timeline ?? []);
      setAnomalies(anomalyJson.anomalies ?? []);
      setQuiet(anomalyJson.quiet ?? []);

      // Track full refresh timestamp
      const recoveredAt = new Date().toISOString();
      setLastFullRefresh(recoveredAt);

      // Phase XX M10: clear degraded on successful HTTP refresh
      setDegraded(false);
      setDegradedReason(null);
      setLastRecoveredAt(recoveredAt);

      // Phase XX M11: report recovered via HTTP
      sendFrontendTelemetry({
        component: "RemediationTimeline",
        event: "recovered",
        tenant: selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown",
      });

      return true;
    } catch (err) {
      console.warn("[timeline] HTTP refresh failed", err);
      return false;
    } finally {
      setLoading(false);
    }
  }, [selectedTenant]);

  // Fetch on mount and when tenant changes
  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // WebSocket: smart incremental update for new remediation events
  useEffect(() => {
    const wsConnection = makeRemediationWS((msg) => {
      if (msg?.type !== "remediation_event") return;

      // Tenant-aware filtering: ignore events from other tenants
      if (selectedTenant && selectedTenant !== "all") {
        const eventTenant = msg.payload?.tenant;
        if (eventTenant && eventTenant !== selectedTenant) {
          return; // Event is for different tenant, skip update
        }
      }

      // Extract timestamp from event payload
      const occurredAt = msg.payload?.occurred_at || msg.payload?.ts;
      if (!occurredAt) {
        // No timestamp available → fallback to full refresh
        console.warn("[timeline] missing timestamp → full refresh");
        fetchTimeline();
        return;
      }

      // Snap timestamp to bucket boundary
      const bucketIso = snapToBucket(occurredAt, BUCKET_MINUTES);

      // Try to increment the matching bucket in memory
      let bucketUpdated = false;
      setData((prev) => {
        if (!prev || prev.length === 0) return prev;

        // Create a shallow copy and find matching bucket
        const next = prev.map((p) => ({ ...p }));
        for (const point of next) {
          if (point.ts === bucketIso) {
            point.count = (point.count ?? 0) + 1;
            bucketUpdated = true;
            break;
          }
        }
        return next;
      });

      if (!bucketUpdated) {
        // Bucket not found (event outside 24h window or timezone mismatch)
        // Fallback to full refresh
        console.warn(`[timeline] bucket ${bucketIso} not found → full refresh`);
        fetchTimeline();
      } else {
        // Successfully updated bucket → refresh anomaly overlay
        // Track WS update timestamp
        setLastWsUpdate(new Date().toISOString());

        // Phase XX M10: WS is alive again, clear degraded
        setWsStale(false);
        setDegraded(false);
        setDegradedReason(null);
        const recoveredAt = new Date().toISOString();
        setLastRecoveredAt(recoveredAt);

        // Phase XX M11: report recovered via WS
        sendFrontendTelemetry({
          component: "RemediationTimeline",
          event: "recovered",
          tenant: selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown",
        });

        // This keeps red dots accurate without refetching timeline
        const params = new URLSearchParams();
        if (selectedTenant && selectedTenant !== "all") {
          params.set("tenant", selectedTenant);
        }
        params.set("window_minutes", "1440");
        params.set("bucket_minutes", "15");

        fetch(`http://localhost:8010/ops/remediations/timeline/anomalies?${params.toString()}`)
          .then((res) => res.json())
          .then((json) => {
            setAnomalies(json.anomalies ?? []);
            setQuiet(json.quiet ?? []);
          })
          .catch((err) => console.warn("anomaly refresh failed", err));
      }
    });

    // Phase XX M9: Send heartbeat every 15 seconds to keep connection alive
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
          console.warn("[timeline] heartbeat send failed", err);
        }
      }
    }, 15000); // 15 seconds

    return () => {
      clearInterval(heartbeatInterval);
      wsConnection.teardown();
    };
  }, [fetchTimeline, selectedTenant]);

  // Phase XX M9: Check for stale connection (no WS update for 35+ seconds)
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
        // Phase XX M11: report WS stale
        sendFrontendTelemetry({
          component: "RemediationTimeline",
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

  // Phase XX M10: WS degradation ladder
  useEffect(() => {
    // only act when we detect staleness
    if (!wsStale) return;

    let cancelled = false;

    (async () => {
      // 1) try HTTP refresh
      const ok = await fetchTimeline();
      if (cancelled) return;

      if (!ok) {
        // 2) mark UI as degraded
        setDegraded(true);
        setDegradedReason("WebSocket stale and HTTP refresh failed");

        const tenantLabel =
          selectedTenant && selectedTenant !== "all" ? selectedTenant : "unknown";

        // M12: first, say HTTP was the thing that failed
        sendFrontendTelemetry({
          component: "RemediationTimeline",
          event: "http_refresh_failed",
          tenant: tenantLabel,
        });

        // then, say we actually ended up degraded
        sendFrontendTelemetry({
          component: "RemediationTimeline",
          event: "degraded",
          tenant: tenantLabel,
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [wsStale, fetchTimeline, selectedTenant]);

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
            marginBottom: "0.75rem",
          }}
        >
          <h3 style={{ fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>
            📈 Remediation Timeline (24h)
          </h3>
          {loading ? (
            <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Loading…</span>
          ) : (
            <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
              {selectedTenant && selectedTenant !== "all" ? selectedTenant : "all tenants"}
            </span>
          )}
        </div>

        {/* Filter controls */}
        <div
          style={{
            display: "flex",
            gap: "0.5rem",
            marginBottom: "1rem",
          }}
        >
          <button
            onClick={() => setFilterMode("all")}
            style={{
              padding: "0.25rem 0.75rem",
              fontSize: "0.75rem",
              borderRadius: "6px",
              border: "1px solid #e5e7eb",
              background: filterMode === "all" ? "#0f766e" : "white",
              color: filterMode === "all" ? "white" : "#374151",
              cursor: "pointer",
              fontWeight: filterMode === "all" ? 600 : 400,
              transition: "all 0.15s",
            }}
          >
            All
          </button>
          <button
            onClick={() => setFilterMode("anomalies")}
            style={{
              padding: "0.25rem 0.75rem",
              fontSize: "0.75rem",
              borderRadius: "6px",
              border: "1px solid #e5e7eb",
              background: filterMode === "anomalies" ? "#dc2626" : "white",
              color: filterMode === "anomalies" ? "white" : "#374151",
              cursor: "pointer",
              fontWeight: filterMode === "anomalies" ? 600 : 400,
              transition: "all 0.15s",
            }}
          >
            Anomalies ({anomalies.length})
          </button>
          <button
            onClick={() => setFilterMode("quiet")}
            style={{
              padding: "0.25rem 0.75rem",
              fontSize: "0.75rem",
              borderRadius: "6px",
              border: "1px solid #e5e7eb",
              background: filterMode === "quiet" ? "#6b7280" : "white",
              color: filterMode === "quiet" ? "white" : "#374151",
              cursor: "pointer",
              fontWeight: filterMode === "quiet" ? 600 : 400,
              transition: "all 0.15s",
            }}
          >
            Quiet ({quiet.length})
          </button>
        </div>
        <div style={{ height: "192px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={filterMode === "all" ? data : filterMode === "anomalies" ? anomalies : quiet}>
              <XAxis
                dataKey="ts"
                tick={{ fontSize: 10 }}
                minTickGap={20}
                tickFormatter={(v) => {
                  // Format as HH:MM
                  try {
                    const date = new Date(v);
                    return date.toLocaleTimeString("en-US", {
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    });
                  } catch {
                    return v.slice(11, 16);
                  }
                }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 10 }}
                width={30}
              />
              <Tooltip
                labelFormatter={(v) => {
                  try {
                    const date = new Date(v);
                    return date.toLocaleString();
                  } catch {
                    return v;
                  }
                }}
                formatter={(value, name) => {
                  if (name === "count") return [`${value} remediations`, "count"];
                  if (name === "baseline") return [`${value} baseline`, "baseline"];
                  if (name === "factor") return [`${value}x spike`, "factor"];
                  return [value, name];
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#0f766e"
                fill="#ccfbf1"
              />
              {/* Anomaly overlay - show red dots on spikes when in "all" mode */}
              {filterMode === "all" && anomalies.length > 0 && (
                <Scatter
                  data={anomalies}
                  dataKey="count"
                  fill="#dc2626"
                  shape="circle"
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Freshness indicators */}
        {(lastWsUpdate || lastFullRefresh) && (
          <div
            style={{
              marginTop: "0.5rem",
              display: "flex",
              gap: "1rem",
              fontSize: "0.65rem",
              color: "#9ca3af",
            }}
          >
            {lastWsUpdate && (
              <span>
                Last WS update: {new Date(lastWsUpdate).toLocaleTimeString()}
              </span>
            )}
            {lastFullRefresh && (
              <span>
                Last full refresh: {new Date(lastFullRefresh).toLocaleTimeString()}
              </span>
            )}
            {/* Phase XX M9: Stale connection warning */}
            {wsStale && (
              <span style={{ color: "#f59e0b", fontWeight: 600 }}>
                ⚠️ WS stale (no updates 35s+)
              </span>
            )}
          </div>
        )}

        {/* Phase XX M10: Degraded mode banner */}
        {degraded && (
          <div
            style={{
              marginTop: "0.35rem",
              fontSize: "0.65rem",
              color: "#fecaca",
              background: "#b91c1c",
              padding: "0.25rem 0.5rem",
              borderRadius: "0.25rem",
              display: "inline-block",
            }}
          >
            ⚠️ Timeline degraded – showing last known data.
            {degradedReason ? ` (${degradedReason})` : null}
            {lastRecoveredAt ? ` Last recovery: ${new Date(lastRecoveredAt).toLocaleTimeString()}` : null}
          </div>
        )}
      </div>
    </div>
  );
};
