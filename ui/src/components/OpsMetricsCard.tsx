import { useEffect, useState } from "react";

type OpsHealth = {
  ok: boolean;
  status?: string;
  started_at?: string;
  uptime_sec?: number;
  degraded?: boolean;
  persistence?: {
    mode?: string;
    dual_write?: boolean;
    last_error?: string | null;
  };
  scheduler?: {
    running?: boolean;
    last_tick_iso?: string | null;
  };
  health?: {
    db?: string;
    replication?: string;
    scheduler?: string;
  };
};

function formatDuration(sec?: number | null): string {
  if (!sec && sec !== 0) return "—";
  if (sec < 0) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function OpsMetricsCard() {
  const [metrics, setMetrics] = useState<OpsHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const res = await fetch("http://localhost:8000/ops/health");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as OpsHealth;
      setMetrics(json);
      setError(null);
    } catch (e: any) {
      // keep last good metrics, just mark error
      setError(e?.message ?? "Failed to load /ops/health");
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  // first-load fallback
  if (!metrics && !error) {
    return (
      <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/40 rounded-lg shadow-sm">
        <div className="text-sm text-slate-500">Loading ops health…</div>
      </div>
    );
  }

  const degraded = metrics?.degraded === true;
  const persistence = metrics?.persistence ?? {};
  const scheduler = metrics?.scheduler ?? {};
  const health = metrics?.health ?? {};

  return (
    <div
      className={
        "card p-4 rounded-lg shadow-sm transition-colors " +
        (degraded
          ? "bg-amber-50 dark:bg-amber-900/30 border border-amber-300/60 dark:border-amber-500/40"
          : "bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/40")
      }
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm">Ops Health</h3>
          {degraded && (
            <span className="text-[0.65rem] px-2 py-0.5 rounded bg-amber-200 text-amber-900 dark:bg-amber-500/20 dark:text-amber-100">
              degraded
            </span>
          )}
          {error && (
            <span className="text-[0.65rem] px-2 py-0.5 rounded bg-red-200 text-red-900 dark:bg-red-500/20 dark:text-red-100">
              backend offline
            </span>
          )}
        </div>
        {metrics?.started_at ? (
          <span className="text-xs text-slate-400">
            since {metrics.started_at}
          </span>
        ) : null}
      </div>

      <div className="space-y-1 text-sm">
        <div className="flex justify-between gap-2">
          <span className="text-slate-500 dark:text-slate-300">🕒 Uptime</span>
          <span className="font-mono text-xs">
            {formatDuration(metrics?.uptime_sec)}
          </span>
        </div>

        <div className="flex justify-between gap-2">
          <span className="text-slate-500 dark:text-slate-300">
            💾 Persistence
          </span>
          <span className="text-xs">
            <span className="font-mono">
              {persistence.mode ?? "json"}
            </span>
            {persistence.dual_write ? " (dual)" : ""}
          </span>
        </div>

        <div className="flex justify-between gap-2">
          <span className="text-slate-500 dark:text-slate-300">
            🧭 Scheduler
          </span>
          <span className="text-xs">
            {scheduler.running ? "running" : "stopped"}
            {scheduler.last_tick_iso ? (
              <span className="text-slate-400 dark:text-slate-500 ml-1">
                {scheduler.last_tick_iso}
              </span>
            ) : null}
          </span>
        </div>

        {/* backend health sources from your legacy block */}
        <div className="flex justify-between gap-2">
          <span className="text-slate-500 dark:text-slate-300">DB</span>
          <span className="text-xs">
            {typeof health.db === "string" ? health.db : "unknown"}
          </span>
        </div>

        {persistence.last_error ? (
          <div className="mt-2 text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-100 rounded p-2">
            ⚠️ {persistence.last_error}
          </div>
        ) : null}
      </div>
    </div>
  );
}
