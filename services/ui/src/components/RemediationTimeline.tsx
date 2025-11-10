import React, { useEffect, useState, useCallback } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { makeRemediationWS } from "../lib/ws";

type TimelinePoint = {
  ts: string;
  count: number;
};

type RemediationTimelineProps = {
  selectedTenant?: string;
};

export const RemediationTimeline: React.FC<RemediationTimelineProps> = ({
  selectedTenant,
}) => {
  const [data, setData] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(false);

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

      const res = await fetch(
        `http://localhost:8010/ops/remediations/timeline?${params.toString()}`
      );
      const json = await res.json();
      setData(json.timeline ?? []);
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
            marginBottom: "1rem",
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
        <div style={{ height: "192px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
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
                formatter={(value) => [`${value} remediations`, "count"]}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#0f766e"
                fill="#ccfbf1"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
