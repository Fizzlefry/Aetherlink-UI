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

  // WebSocket: smart incremental update for new remediation events
  useEffect(() => {
    const teardown = makeRemediationWS((msg) => {
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
        console.log("remediation_event without timestamp, doing full refresh");
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
        console.log(`bucket ${bucketIso} not found, doing full refresh`);
        fetchTimeline();
      } else {
        // Successfully updated bucket → refresh anomaly overlay
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

    return teardown;
  }, [fetchTimeline, selectedTenant]);

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
