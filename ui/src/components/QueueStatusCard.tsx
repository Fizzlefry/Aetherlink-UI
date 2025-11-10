import { useEffect, useState } from "react";

type QueueData = {
    alerts: { pending: number; dead_letter: number };
    events: { pending: number; backlog_minutes: number };
    replication: { pending: number; backlog_minutes: number };
};

type QueuesResponse = {
    ok: boolean;
    queues?: QueueData;
    tenant?: string | null;
};

type QueueStatusCardProps = {
    tenant?: string | null;
};

export function QueueStatusCard({ tenant }: QueueStatusCardProps = {}) {
    const [data, setData] = useState<QueueData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setLoading(true);
        try {
            const url = tenant
                ? `http://localhost:8000/ops/operator/queues?tenant=${encodeURIComponent(tenant)}`
                : "http://localhost:8000/ops/operator/queues";
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const response: QueuesResponse = await res.json();
            setData(response.queues ?? null);
            setError(null);
        } catch (e: any) {
            setError(e?.message ?? "Failed to load queue status");
        } finally {
            setLoading(false);
        }
    } useEffect(() => {
        load();
        // Auto-refresh every 30 seconds
        const interval = setInterval(load, 30000);
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200/60 dark:border-slate-700/40 shadow-sm">
                <h3 className="font-semibold text-sm mb-2">Queue Status</h3>
                <p className="text-sm text-slate-500">Loading queues…</p>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200/60 dark:border-slate-700/40 shadow-sm">
                <h3 className="font-semibold text-sm mb-2">Queue Status</h3>
                <p className="text-sm text-red-400">⚠ {error || "No data"}</p>
            </div>
        );
    }

    // Defensive JSON shapes
    const alerts = data?.alerts ?? { pending: 0, dead_letter: 0 };
    const events = data?.events ?? { pending: 0, backlog_minutes: 0 };
    const replication = data?.replication ?? { pending: 0, backlog_minutes: 0 };

    const hasIssues = alerts.dead_letter > 0 || events.backlog_minutes > 5 || replication.backlog_minutes > 5;

    return (
        <div className={`card p-4 rounded-lg border shadow-sm ${hasIssues ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700/40' : 'bg-slate-50 dark:bg-slate-900/60 border-slate-200/60 dark:border-slate-700/40'}`}>
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">Queue Status</h3>
                <button
                    onClick={load}
                    className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    title="Refresh"
                >
                    ↻
                </button>
            </div>

            <div className="space-y-3">
                {/* Alerts */}
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Alerts pending</p>
                        <p className="text-lg font-mono text-slate-900 dark:text-slate-100">
                            {alerts.pending}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Dead letters</p>
                        <p className={`text-lg font-mono ${alerts.dead_letter > 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-slate-100'}`}>
                            {alerts.dead_letter}
                        </p>
                    </div>
                </div>

                {/* Events */}
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Events pending</p>
                        <p className="text-lg font-mono text-slate-900 dark:text-slate-100">
                            {events.pending}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Backlog (min)</p>
                        <p className={`text-lg font-mono ${events.backlog_minutes > 5 ? 'text-orange-600 dark:text-orange-400' : 'text-slate-900 dark:text-slate-100'}`}>
                            {events.backlog_minutes}
                        </p>
                    </div>
                </div>

                {/* Replication */}
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Replication pending</p>
                        <p className="text-lg font-mono text-slate-900 dark:text-slate-100">
                            {replication.pending}
                        </p>
                    </div>
                    <div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Backlog (min)</p>
                        <p className={`text-lg font-mono ${replication.backlog_minutes > 5 ? 'text-orange-600 dark:text-orange-400' : 'text-slate-900 dark:text-slate-100'}`}>
                            {replication.backlog_minutes}
                        </p>
                    </div>
                </div>
            </div>

            {hasIssues && (
                <div className="mt-3 text-xs text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30 p-2 rounded">
                    ⚠ Queue issues detected - check system health
                </div>
            )}
        </div>
    );
}
