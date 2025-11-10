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

export const RemediationTimeline: React.FC<RemediationTimelineProps> = ({
  selectedTenant,
}) => {
  const [data, setData] = useState<TimelinePoint[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyPoint[]>([]);
  const [quiet, setQuiet] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");

  const fetchTimeline = useCallback(async () => {
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
    } catch (err) {
      console.error("timeline fetch failed", err);
    } finally {
      setLoading(false);
    }
  }, [selectedTenant]);

  // Fetch on mount and when tenant changes
  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  // WebSocket: refresh on new remediation event
  useEffect(() => {
    const teardown = makeRemediationWS((msg) => {
      if (msg?.type === "remediation_event") {
        fetchTimeline();
      }
    });
    return teardown;
  }, [fetchTimeline]);

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
      </div>
    </div>
  );
};
