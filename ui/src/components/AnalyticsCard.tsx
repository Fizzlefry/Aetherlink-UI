import { useEffect, useState } from "react";

type AnalyticsPayload = {
  ok: boolean;
  ts_iso?: string;
  totals?: {
    audit_entries?: number;
    schedules?: number;
  };
  groups?: Record<string, { all_time: number; last_24h: number }>;
  trends?: Record<string, "up" | "down" | "flat">;
};

type TrendsPayload = {
  ok: boolean;
  tenant?: string | null;
  window_days: number;
  current: {
    totals: { all_time: number; last_24h: number };
    groups: Record<string, { all_time: number; last_24h: number }>;
    trends: Record<string, "up" | "down" | "flat">;
  };
  analysis: {
    rolling_averages: Record<string, { rolling_avg: number; rate_delta: number }>;
    forecasts: Record<string, { forecast_value: number; confidence: number }>;
    anomalies?: any[];
  };
};

type AnalyticsCardProps = {
  tenant?: string | null;
};

export function AnalyticsCard({ tenant }: AnalyticsCardProps = {}) {
  const [metrics, setMetrics] = useState<AnalyticsPayload | null>(null);
  const [trendsData, setTrendsData] = useState<TrendsPayload | null>(null);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState<number>(30000); // 30s default

  async function load() {
    try {
      // Load basic analytics
      const url = tenant
        ? `http://localhost:8000/ops/analytics?tenant=${encodeURIComponent(tenant)}`
        : "http://localhost:8000/ops/analytics";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as AnalyticsPayload;
      setMetrics(json);

      // Load trends data
      const trendsUrl = tenant
        ? `http://localhost:8000/ops/analytics/trends?tenant=${encodeURIComponent(tenant)}`
        : "http://localhost:8000/ops/analytics/trends";
      const trendsRes = await fetch(trendsUrl);
      if (trendsRes.ok) {
        const trendsJson = (await trendsRes.json()) as TrendsPayload;
        setTrendsData(trendsJson);

        // Capture anomalies if present
        const detected =
          trendsJson?.analysis?.anomalies && Array.isArray(trendsJson.analysis.anomalies)
            ? trendsJson.analysis.anomalies
            : [];
        setAnomalies(detected);
      }

      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load analytics");
    }
  }

  useEffect(() => {
    load();
    if (refreshInterval > 0) {
      const id = setInterval(load, refreshInterval);
      return () => clearInterval(id);
    }
  }, [refreshInterval]);

  if (!metrics && !error) {
    return (
      <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200/60 dark:border-slate-700/40 shadow-sm">
        <div className="text-sm text-slate-500">Loading analytics…</div>
      </div>
    );
  }

  const { totals = {}, groups = {}, trends = {} } = metrics || {};

  return (
    <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200/60 dark:border-slate-700/40 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center">
          Analytics
          {anomalies.length > 0 && (
            <span className="ml-2 inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
              {anomalies.length} anomaly{anomalies.length > 1 ? 'ies' : ''}
            </span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="text-xs bg-slate-100 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded px-2 py-0.5"
            title="Auto-refresh interval"
          >
            <option value={0}>Manual</option>
            <option value={30000}>30s</option>
            <option value={60000}>1m</option>
          </select>
          {metrics?.ts_iso ? (
            <span className="text-xs text-slate-400">{metrics.ts_iso}</span>
          ) : null}
        </div>
      </div>

      {anomalies.length > 0 && (
        <div className="mb-3 rounded-md bg-amber-100 border border-amber-200 px-3 py-2 text-sm text-amber-900 flex items-start gap-2">
          <span className="mt-0.5 text-amber-700">⚠</span>
          <div>
            <div className="font-medium">Predictive Ops: attention needed</div>
            <div className="text-xs text-amber-800">
              {anomalies[0]?.message ?? 'One or more anomalies were detected in the latest trends.'}
            </div>
            {anomalies.length > 1 && (
              <div className="text-[10px] text-amber-700 mt-1">
                +{anomalies.length - 1} more
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        {/* All-time */}
        <div>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            All-time
          </div>
          <div className="space-y-0.5">
            <div className="flex justify-between">
              <span className="text-slate-600 dark:text-slate-300">
                Audit entries
              </span>
              <span className="font-mono text-xs">
                {totals.audit_entries ?? 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600 dark:text-slate-300">
                Schedules
              </span>
              <span className="font-mono text-xs">
                {totals.schedules ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Last 24h */}
        <div>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            Last 24h
          </div>
          <div className="space-y-0.5">
            {Object.entries(groups).length > 0 ? (
              Object.entries(groups).map(([op, data]) => {
                const trend = trends[op] || "flat";
                const trendIcon = trend === "up" ? "▲" : trend === "down" ? "▼" : "◆";
                const trendColor = trend === "up" ? "text-green-500" : trend === "down" ? "text-red-500" : "text-slate-400";
                return (
                  <div key={op} className="flex justify-between items-center">
                    <span className="text-slate-600 dark:text-slate-300 break-all flex-1 mr-2">
                      {op}
                    </span>
                    <div className="flex items-center gap-1">
                      <span className={`text-xs ${trendColor}`}>{trendIcon}</span>
                      <span className="font-mono text-xs">{data.last_24h}</span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-xs text-slate-400">
                No recent activity
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Operations breakdown */}
      <div className="pt-3 border-t border-slate-200/60 dark:border-slate-700/40">
        <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
          Operations
        </div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(groups).map(([op, data]) => (
            <span
              key={op}
              className="text-xs px-2 py-0.5 bg-slate-200 dark:bg-slate-700 rounded"
            >
              {op}: {data.all_time}
            </span>
          ))}
          {Object.keys(groups).length === 0 ? (
            <span className="text-xs text-slate-400">No data</span>
          ) : null}
        </div>
      </div>

      {/* Predictive Analytics */}
      {trendsData?.analysis && (
        <div className="pt-3 border-t border-slate-200/60 dark:border-slate-700/40">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            Predictive Analytics
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {/* Current vs Forecast */}
            <div>
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                Ops last 24h
              </div>
              <div className="font-mono text-lg">
                {trendsData.current.totals.last_24h}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
                Forecast next 24h
              </div>
              <div className="font-mono text-lg">
                {Object.values(trendsData.analysis.forecasts).reduce((sum, f) => sum + Math.round(f.forecast_value), 0)}
              </div>
            </div>
          </div>

          {/* Trend indicators */}
          <div className="mt-3">
            <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
              Operation Trends
            </div>
            <div className="space-y-1">
              {Object.entries(trendsData.analysis.rolling_averages).map(([op, data]) => {
                const forecast = trendsData.analysis.forecasts[op];
                const current = trendsData.current.groups[op]?.last_24h || 0;
                const trend = current > data.rolling_avg ? "up" : current < data.rolling_avg ? "down" : "flat";
                const trendIcon = trend === "up" ? "📈" : trend === "down" ? "📉" : "➡️";
                const trendColor = trend === "up" ? "text-green-500" : trend === "down" ? "text-red-500" : "text-slate-400";

                return (
                  <div key={op} className="flex justify-between items-center text-xs">
                    <span className="text-slate-600 dark:text-slate-300 break-all flex-1 mr-2">
                      {op}
                    </span>
                    <div className="flex items-center gap-1">
                      <span className={trendColor}>{trendIcon}</span>
                      <span className="text-slate-500">
                        {Math.round(data.rate_delta * 24)}/day
                      </span>
                      {forecast && (
                        <span className="text-slate-400 ml-1">
                          ({Math.round(forecast.confidence * 100)}% conf)
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {Object.keys(trendsData.analysis.rolling_averages).length === 0 && (
                <div className="text-xs text-slate-400">
                  No trend data available
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Phase XXXIV: Auto-Healing Controls */}
      <div className="pt-3 border-t border-slate-200/60 dark:border-slate-700/40">
        <div className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
          Auto-Healing
        </div>
        <div className="flex items-center justify-between">
          <div className="text-xs text-slate-600 dark:text-slate-300">
            Automatic remediation for anomaly alerts
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              defaultChecked={true}
              className="w-3 h-3 text-blue-600 bg-slate-100 border-slate-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-slate-800 focus:ring-2 dark:bg-slate-700 dark:border-slate-600"
              title="Enable automatic remediation for anomaly alerts"
            />
            <span className="text-xs text-slate-600 dark:text-slate-300">Enabled</span>
          </label>
        </div>
        <div className="mt-2 text-[10px] text-slate-400">
          When enabled, anomaly alerts trigger automatic corrective actions
        </div>
      </div>

      {error ? (
        <div className="text-xs text-red-400 mt-1">⚠ {error}</div>
      ) : null}
    </div>
  );
}
