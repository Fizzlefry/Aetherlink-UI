import React, { useEffect, useState } from "react";

type MediaStatsResponse = {
  summary?: {
    total_files: number;
    total_size_mb: number;
    uploads_today: number;
  };
  details?: {
    uploads_last_24h: number;
    total_size_bytes: number;
    by_mime_type: Record<string, number>;
    timestamp: string;
  };
  // flat fallback fields
  total_files?: number;
  total_size_mb?: number;
  uploads_today?: number;
};

/**
 * MediaStatsBadge
 * Compact header badge showing basic media upload metrics.
 *
 * Displays:
 *  - uploads_today
 *  - total_size_mb (2 decimals)
 *
 * Behavior:
 *  - Polls /uploads/stats every 30s.
 *  - Prefers summary.* fields, falls back to flat fields for backward compatibility.
 *  - Shows a small "media offline" indicator on fetch error.
 *
 * Used in Command Center header for at-a-glance media status.
 *
 * Props:
 *  - className?: string — optional style override or layout wrapper
 */
type MediaStatsBadgeProps = {
  className?: string;
};

export const MediaStatsBadge: React.FC<MediaStatsBadgeProps> = ({ className = "" }) => {
  const [stats, setStats] = useState<MediaStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);

  const fetchStats = async () => {
    try {
      const res = await fetch("http://localhost:9109/uploads/stats");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: MediaStatsResponse = await res.json();
      setStats(json);
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Unavailable");
    }
  };

  useEffect(() => {
    fetchStats();
    const id = setInterval(fetchStats, 30000); // 30s cadence
    return () => clearInterval(id);
  }, []);

  // prefer summary, fall back to flat fields
  const uploadsToday = stats?.summary?.uploads_today ?? stats?.uploads_today ?? 0;
  const totalSizeMb = stats?.summary?.total_size_mb ?? stats?.total_size_mb ?? 0;
  const uploadsLast24h = stats?.details?.uploads_last_24h ?? (stats as any)?.uploads_last_24h ?? 0;
  const timestamp = stats?.details?.timestamp ?? (stats as any)?.timestamp ?? null;

  return (
    <div
      className={`relative ${className}`}
      style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Uploads Today */}
      <div
        title="Uploads Today"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 0.75rem",
          background: "#eef2ff",
          color: "#3730a3",
          border: "1px solid #c7d2fe",
          borderRadius: "9999px",
          fontWeight: 600,
          fontSize: "0.875rem",
        }}
      >
        <span>Uploads Today</span>
        <span style={{
          background: "white",
          color: "#111827",
          border: "1px solid #e5e7eb",
          borderRadius: "9999px",
          padding: "0.125rem 0.5rem",
          minWidth: 24,
          textAlign: "center",
        }}>{uploadsToday}</span>
      </div>

      {/* Total Size (MB) */}
      <div
        title="Total Size (MB)"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 0.75rem",
          background: "#ecfdf5",
          color: "#065f46",
          border: "1px solid #a7f3d0",
          borderRadius: "9999px",
          fontWeight: 600,
          fontSize: "0.875rem",
        }}
      >
        <span>Total Size</span>
        <span style={{
          background: "white",
          color: "#111827",
          border: "1px solid #e5e7eb",
          borderRadius: "9999px",
          padding: "0.125rem 0.5rem",
          minWidth: 48,
          textAlign: "center",
        }}>{totalSizeMb.toFixed(2)} MB</span>
      </div>

      {/* Error state (non-blocking) */}
      {error && (
        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>({error})</span>
      )}

      {showTooltip && !error && (
        <div className="absolute z-20 mt-2 w-56 rounded-md bg-white dark:bg-slate-900 p-3 text-xs shadow-lg border border-slate-200 dark:border-slate-700 right-0 top-full text-slate-900 dark:text-slate-100">
          <p className="font-semibold mb-2">Media stats</p>
          <p>
            <span className="text-slate-500">Updated:</span> {timestamp ?? "—"}
          </p>
          <p>
            <span className="text-slate-500 dark:text-slate-400">Last 24h:</span> {uploadsLast24h}
          </p>
          <p className="text-slate-500 dark:text-slate-400 mt-2">Source: /uploads/stats</p>
        </div>
      )}
    </div>
  );
};

export default MediaStatsBadge;
