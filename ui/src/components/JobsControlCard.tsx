import { useEffect, useState } from "react";

type Job = {
    id: string;
    name: string;
    status: "running" | "paused";
    next_run: string | null;
};

type JobsResponse = {
    ok: boolean;
    jobs?: Job[];
    items?: Job[];
};

type JobsControlCardProps = {
    tenant?: string | null;
};

export function JobsControlCard({ tenant }: JobsControlCardProps = {}) {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setLoading(true);
        try {
            const url = tenant
                ? `http://localhost:8000/ops/operator/jobs?tenant=${encodeURIComponent(tenant)}`
                : "http://localhost:8000/ops/operator/jobs";
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: JobsResponse = await res.json();
            setJobs(data.jobs ?? data.items ?? []);
            setError(null);
        } catch (e: any) {
            setError(e?.message ?? "Failed to load jobs");
        } finally {
            setLoading(false);
        }
    }

    async function action(jobId: string, op: "pause" | "resume") {
        // Optimistic update
        setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: op === "pause" ? "paused" : "running" } : j));

        try {
            const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
            const res = await fetch(`http://localhost:8000/ops/operator/jobs/${jobId}/${op}${qs}`, {
                method: "POST",
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            await load(); // Refresh the list to get latest state
        } catch (e: any) {
            // Rollback on error
            await load();
            setError(`Failed to ${op} job: ${e?.message}`);
        }
    }

    useEffect(() => {
        load();
    }, []);

    return (
        <div className="card p-4 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200/60 dark:border-slate-700/40 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm">Scheduler Control</h3>
                <button
                    onClick={load}
                    className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    title="Refresh"
                >
                    ↻
                </button>
            </div>

            {loading ? (
                <p className="text-sm text-slate-500">Loading jobs…</p>
            ) : error ? (
                <p className="text-sm text-red-400">⚠ {error}</p>
            ) : (
                <div className="space-y-2">
                    {jobs.map((job) => (
                        <div key={job.id} className="flex items-center justify-between gap-3 p-2 bg-white dark:bg-slate-800/50 rounded border border-slate-200 dark:border-slate-700">
                            <div className="flex-1">
                                <p className="text-sm text-slate-900 dark:text-slate-100 font-medium">{job.name}</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400">{job.id}</p>
                                {job.next_run && (
                                    <p className="text-xs text-slate-400 dark:text-slate-500">Next: {job.next_run}</p>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                <span className={`text-xs px-2 py-0.5 rounded-full ${job.status === "running"
                                    ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                                    : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                                    }`}>
                                    {job.status}
                                </span>
                                {job.status === "running" ? (
                                    <button
                                        onClick={() => action(job.id, "pause")}
                                        className="text-xs bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 px-2 py-1 rounded transition-colors"
                                    >
                                        Pause
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => action(job.id, "resume")}
                                        className="text-xs bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-800/50 text-blue-700 dark:text-blue-300 px-2 py-1 rounded transition-colors"
                                    >
                                        Resume
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                    {jobs.length === 0 && (
                        <p className="text-sm text-slate-500 text-center py-4">No jobs for this scope.</p>
                    )}
                </div>
            )}
        </div>
    );
}
