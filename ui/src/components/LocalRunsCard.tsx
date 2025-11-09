import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function LocalRunsCard() {
  const [runs, setRuns] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await api("/api/local/runs");
        const json = await res.json();
        if (!cancelled) {
          setRuns(json.runs ?? []);
          setError(null);
          setLoading(false);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message ?? "Failed to load runs");
          setLoading(false);
        }
      }
    }

    load();
    const id = setInterval(load, 30000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (loading) return <div className="card p-4">Loading local runs…</div>;

  if (error)
    return (
      <div className="card p-4 bg-red-100 text-red-800">
        Failed to load local runs
        <div className="text-xs mt-1">{error}</div>
      </div>
    );

  return (
    <div className="card p-4 bg-white shadow-sm rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-lg">Recent Local Runs</h2>
        <span className="text-xs text-slate-400">
          showing {runs.length} item{runs.length === 1 ? "" : "s"}
        </span>
      </div>
      {runs.length === 0 ? (
        <div className="text-sm text-slate-500">No runs recorded.</div>
      ) : (
        <ul className="space-y-2 text-sm max-h-48 overflow-y-auto">
          {runs.map((r, idx) => (
            <li key={idx} className="flex justify-between gap-2">
              <div>
                <div className="font-mono text-xs">
                  {r.name ?? r.id ?? "run"}
                </div>
                {r.status ? (
                  <div className="text-xs text-slate-400">{r.status}</div>
                ) : null}
              </div>
              <div className="text-xs text-slate-400">
                {r.ts_iso ?? r.ts ?? ""}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
