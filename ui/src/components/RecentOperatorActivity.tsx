import * as React from "react";

type OperatorEvent = {
    ts: string;               // ISO timestamp
    ts_iso: string;           // ISO timestamp
    operation: string;        // e.g. "operator.job.paused"
    tenant?: string;
    metadata?: Record<string, unknown>;
    actor?: string;
}; interface RecentOperatorActivityProps {
    tenant?: string | null;
}

export function RecentOperatorActivity({ tenant }: RecentOperatorActivityProps) {
    const [events, setEvents] = React.useState<OperatorEvent[]>([]);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);

    const load = React.useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
            const res = await fetch(`/ops/operator/recent${qs}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // expect { ok: true, tenant, events: [...] }
            const list = data.events ?? data.items ?? [];
            setEvents(list);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Unable to load recent operator activity.");
        } finally {
            setLoading(false);
        }
    }, [tenant]);

    React.useEffect(() => {
        load();
        // optional: auto-refresh every 60s
        const id = setInterval(load, 60000);
        return () => clearInterval(id);
    }, [load]); return (
        <div className="rounded-xl bg-slate-900/40 border border-slate-700 p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
                <h2 className="text-slate-100 font-semibold text-sm">
                    Recent Operator Activity
                </h2>
                <button
                    onClick={load}
                    className="text-xs text-slate-300 hover:text-white"
                >
                    Refresh
                </button>
            </div>

            {loading ? (
                <p className="text-slate-400 text-sm">Loading…</p>
            ) : error ? (
                <p className="text-red-300 text-xs">{error}</p>
            ) : events.length === 0 ? (
                <p className="text-slate-500 text-sm">
                    No operator actions{tenant ? ` for ${tenant}` : ""} yet.
                </p>
            ) : (
                <ul className="flex flex-col gap-2">
                    {events.slice(0, 10).map((ev, idx) => {
                        const ts = ev.ts_iso
                            ? new Date(ev.ts_iso).toLocaleString()
                            : "—";
                        const op = ev.operation ?? "operator.action";
                        const actor = ev.actor ?? "aether-operator-ui";
                        const jobName = String(
                            ev.metadata?.job_name ??
                            ev.metadata?.job_id ??
                            "Job"
                        );

                        // color by action
                        const isPause = op.includes("paused");
                        const isResume = op.includes("resumed");
                        const badgeClass = isPause
                            ? "bg-amber-500/20 text-amber-100"
                            : isResume
                                ? "bg-emerald-500/20 text-emerald-100"
                                : "bg-slate-600/50 text-slate-100";

                        return (
                            <li
                                key={idx}
                                className="flex items-start justify-between gap-3"
                            >
                                <div className="flex flex-col gap-0.5">
                                    <div className="flex items-center gap-2">
                                        <span
                                            className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${badgeClass}`}
                                        >
                                            {op.replace("operator.", "").replace("job.", "")}
                                        </span>
                                        {tenant ? (
                                            <span className="text-[10px] text-slate-500">
                                                {tenant}
                                            </span>
                                        ) : ev.tenant ? (
                                            <span className="text-[10px] text-slate-500">
                                                {ev.tenant}
                                            </span>
                                        ) : null}
                                    </div>
                                    <p className="text-sm text-slate-100">
                                        {jobName}
                                    </p>
                                    <p className="text-[11px] text-slate-500">
                                        {ts} • {actor}
                                    </p>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
