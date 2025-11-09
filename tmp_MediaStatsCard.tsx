import React, { useEffect, useState } from "react";

type MediaStats = {
  summary?: {
    total_files: number;
    total_size_mb: number;
    uploads_today: number;
  };
  details?: {
    total_size_bytes: number;
    uploads_last_24h: number;
    by_mime_type: Record<string, number>;
    timestamp: string;
  };
  // flat (back-compat)
  total_files?: number;
  total_size_mb?: number;
  uploads_today?: number;
  uploads_last_24h?: number;
};

type MediaStatsCardProps = {
  jobId?: string | number;
  className?: string;
};

/**
 * MediaStatsCard
 * Displays media upload metrics and optional deep-link to job-specific uploads.
 *
 * Props:
 *  - jobId?: string | number  â†’ when provided, opens /uploads?job_id={jobId}
 *  - className?: string â†’ optional style override or layout wrapper
 *  - polls /uploads/stats every 30s (prefers summary.* fields)
 *
 * Used in Operator Dashboard and (optionally) job detail views.
 */
export function MediaStatsCard({ jobId, className = "" }: MediaStatsCardProps) {
  
  const [data, setData] = useState<MediaStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchStats() {
      try {
        const res = await fetch("http://localhost:9109/uploads/stats");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (isMounted) {
          setData(json);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          setError("Media service offline");
        }
      }
    }

    fetchStats();
    const id = setInterval(fetchStats, 30000);
    return () => {
      isMounted = false;
      clearInterval(id);
    };
  }, []);

  const totalSizeMb =
    data?.summary?.total_size_mb ??
    data?.total_size_mb ??
    0;

  const uploadsLast24h =
    data?.details?.uploads_last_24h ??
    data?.uploads_last_24h ??
    0;

  const uploadsToday =
    data?.summary?.uploads_today ??
    data?.uploads_today ??
    0;

  // Top MIME types (up to 3)
  const topMimeEntries = (() => {
    const byMime = data?.details?.by_mime_type || {};
    const entries = Object.entries(byMime).filter(([k]) => k);
    entries.sort((a, b) => (b[1] as number) - (a[1] as number));
    return entries.slice(0, 3) as [string, number][];
  })();

  // Staleness indicator (older than 2 minutes)
  const timestampStr: string | null = data?.details?.timestamp ?? null;
  const timestamp = timestampStr ? new Date(timestampStr) : null;
  const isStale = !!(timestamp && (Date.now() - timestamp.getTime() > 2 * 60 * 1000));

  return (
    <div className={`rounded-xl border bg-white dark:bg-slate-900 dark:border-slate-700 backdrop-blur p-4 flex flex-col gap-3 min-w-[240px] ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Media</h2>
          {error ? (
            <span className="text-xs text-red-500">{error}</span>
          ) : (
            <>
              <span className="text-xs text-slate-400 dark:text-slate-400">
                {timestamp ? timestamp.toLocaleTimeString() : "â€”"}
              </span>
              {isStale && (
                <span className="text-xs text-amber-500 ml-1">(stale)</span>
              )}
            </>
          )}
          {/* Info tooltip trigger */}
          <div
            className="relative"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-200 dark:bg-slate-700 text-[10px] font-bold text-slate-700 dark:text-slate-100 cursor-default">i</span>
            {showTooltip && !error && (
              <div className="absolute z-20 mt-2 w-64 rounded-md bg-white dark:bg-slate-900 p-3 text-xs shadow-lg border border-slate-200 dark:border-slate-700 right-0 text-slate-900 dark:text-slate-100">
                <p className="font-semibold mb-2">Media details</p>
                <p>
                  <span className="text-slate-500">Updated:</span> {timestamp ? timestamp.toLocaleString() : "â€”"}
                </p>
                <p>
                  <span className="text-slate-500 dark:text-slate-400">Last 24h:</span> {uploadsLast24h}
                </p>
                {topMimeEntries.length > 0 && (
                  <div className="mt-2">
                    <p className="text-slate-500 dark:text-slate-400 mb-1">Top MIME types:</p>
                    <div className="flex flex-wrap gap-1">
                      {topMimeEntries.map(([mime, count]) => (
                        <span key={mime} className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] text-slate-700 dark:text-slate-100">
                          {mime} Â· {count}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        <a
          href={jobId ? `http://localhost:9109/uploads?job_id=${jobId}` : "http://localhost:9109/uploads"}
          className="text-xs text-indigo-600 dark:text-blue-400 hover:underline"
          target="_blank"
          rel="noreferrer"
        >
          {jobId ? `View job #${jobId} uploads ->` : "View uploads ->"}
        </a>
      </div>

      <div className="flex gap-4">
        <div>
          <p className="text-[0.65rem] uppercase tracking-wide text-slate-400 dark:text-slate-400">Last 24h</p>
          <p className="text-xl font-semibold text-slate-900 dark:text-slate-100">{uploadsLast24h}</p>
        </div>
        <div>
          <p className="text-[0.65rem] uppercase tracking-wide text-slate-400 dark:text-slate-400">Today</p>
          <p className="text-xl font-semibold text-slate-900 dark:text-slate-100">{uploadsToday}</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
        <span>Total size</span>
        <span className="font-medium text-slate-900 dark:text-slate-100">
          {Number(totalSizeMb).toFixed(2)} MB
        </span>
      </div>

      {topMimeEntries.length > 0 && (
        <div className="text-sm text-slate-600 dark:text-slate-300">
          <div className="text-[0.65rem] uppercase tracking-wide text-slate-400 dark:text-slate-400 mb-1">Top types</div>
          <div className="flex flex-wrap gap-2">
            {topMimeEntries.map(([mime, count]) => (
              <span key={mime} className="px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-100 text-xs">
                {mime} Â· {count}
              </span>
            ))}
          </div>
        </div>
      )}

      
    </div>
  );
}

export default MediaStatsCard;
