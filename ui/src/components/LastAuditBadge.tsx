import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function LastAuditBadge() {
  const [event, setEvent] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await api("/api/crm/import/acculynx/audit?limit=1");
        const json = await res.json();
        if (!cancelled) {
          const audit = json.audit ?? [];
          setEvent(audit[0] ?? null);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message ?? "Failed to load audit");
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

  if (error) {
    return (
      <div className="text-xs text-red-500">
        Audit unavailable: {error}
      </div>
    );
  }

  if (!event) {
    return (
      <div className="text-xs text-slate-400">
        No recent scheduler activity
      </div>
    );
  }

  return (
    <div className="text-xs text-slate-600">
      <span className="font-mono text-slate-500">
        {event.ts_iso ?? event.ts}
      </span>
      {' • '}
      <span className="font-medium">{event.tenant}</span>
      {' • '}
      <span className="px-1 rounded bg-slate-100 text-slate-600">
        {event.operation}
      </span>
    </div>
  );
}
