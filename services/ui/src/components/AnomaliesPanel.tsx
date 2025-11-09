import React, { useEffect, useState } from "react";
import {
  fetchCurrentAnomalies,
  fetchDeliveryHistory,
  type AnomaliesResponse,
  type DeliveryHistoryItem,
} from "../commandCenterApi";

type Severity = "critical" | "warning" | "info";

function severityColor(sev: Severity) {
  switch (sev) {
    case "critical":
      return "bg-red-100 text-red-800 border-red-200";
    case "warning":
      return "bg-amber-100 text-amber-800 border-amber-200";
    default:
      return "bg-slate-100 text-slate-800 border-slate-200";
  }
}

export const AnomaliesPanel: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [anomalies, setAnomalies] = useState<AnomaliesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // optional: show the last few deliveries to correlate
  const [deliveries, setDeliveries] = useState<DeliveryHistoryItem[]>([]);

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true);
      try {
        const [a, d] = await Promise.all([
          fetchCurrentAnomalies("admin"),
          fetchDeliveryHistory({ limit: 5 }, "operator"),
        ]);
        if (!alive) return;
        setAnomalies(a);
        setDeliveries(d.items ?? []);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        setError(e.message || "Failed to load anomalies");
      } finally {
        if (alive) setLoading(false);
      }
    }
    load();

    // small auto-refresh every 30s so operators see new incidents
    const id = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Anomalies</h2>
          <p className="text-xs text-slate-500">
            Live signal from Command Center ( /anomalies/current )
          </p>
        </div>
        {loading ? (
          <span className="text-xs text-slate-400">Refreshing…</span>
        ) : null}
      </div>

      {error ? (
        <div className="text-sm text-red-500 bg-red-50 border border-red-100 rounded-lg p-3">
          {error}
        </div>
      ) : null}

      {!loading && anomalies && anomalies.incidents?.length === 0 ? (
        <div className="text-sm text-slate-500 bg-slate-50 rounded-lg p-3">
          No incidents detected in the last {anomalies.window_minutes} minutes.
        </div>
      ) : null}

      {/* Summary badges */}
      {anomalies && anomalies.summary.total_incidents > 0 ? (
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded-lg bg-red-100 text-red-800 font-medium">
            {anomalies.summary.critical_incidents} critical
          </span>
          <span className="px-2 py-1 rounded-lg bg-amber-100 text-amber-800 font-medium">
            {anomalies.summary.warning_incidents} warnings
          </span>
        </div>
      ) : null}

      {/* incidents list */}
      <div className="flex flex-col gap-2">
        {anomalies?.incidents?.map((inc: any, idx: number) => (
          <div
            key={inc.id ?? inc.code ?? idx}
            className={`rounded-xl border px-3 py-2 flex flex-col gap-1 ${severityColor(
              (inc.severity ?? "info") as Severity
            )}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-sm">
                {inc.type ?? inc.metric_name ?? "Anomaly detected"}
              </span>
              <span className="text-xs opacity-80">
                {anomalies.detected_at
                  ? new Date(anomalies.detected_at).toLocaleTimeString()
                  : ""}
              </span>
            </div>
            {inc.message ? (
              <p className="text-xs leading-snug">{inc.message}</p>
            ) : null}
            {inc.affected_tenant ? (
              <p className="text-[11px] mt-1 opacity-75">
                Tenant: <code>{inc.affected_tenant}</code>
              </p>
            ) : null}
            {inc.affected_endpoint ? (
              <p className="text-[11px] opacity-75">
                Endpoint: <code>{inc.affected_endpoint}</code>
              </p>
            ) : null}
          </div>
        ))}
      </div>

      {/* tiny correlation block */}
      <div className="mt-2">
        <h3 className="text-xs font-semibold text-slate-500 mb-1">
          Recent deliveries (for context)
        </h3>
        <div className="flex flex-col gap-1 max-h-36 overflow-y-auto">
          {deliveries.map((d: DeliveryHistoryItem) => (
            <div
              key={d.id}
              className="flex items-center justify-between text-xs border-b last:border-b-0 py-1"
            >
              <div className="flex flex-col">
                <span className="font-medium">{d.rule_name}</span>
                <span className="text-slate-400">
                  {d.event_type} → {d.status}
                </span>
              </div>
              <span className="text-[10px] text-slate-400">
                {d.created_at
                  ? new Date(d.created_at).toLocaleTimeString()
                  : ""}
              </span>
            </div>
          ))}
          {deliveries.length === 0 ? (
            <div className="text-xs text-slate-400 italic">No deliveries.</div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
