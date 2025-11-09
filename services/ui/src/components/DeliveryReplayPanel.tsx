import React, { useEffect, useState } from "react";
import {
  fetchDeliveryHistory,
  replayDelivery,
  type DeliveryHistoryItem,
} from "../commandCenterApi";

export const DeliveryReplayPanel: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<DeliveryHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchDeliveryHistory({ limit: 10 }, "operator");
      setItems(data.items ?? []);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? "Failed to load deliveries");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // Auto-refresh every 30s
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  async function handleReplay(id: string) {
    setActionMessage(null);
    try {
      const result = await replayDelivery(id, "admin");
      setActionMessage(`✅ Replay queued for delivery ${id.slice(0, 8)}...`);
      // Re-pull so status updates
      await load();
    } catch (e: any) {
      setActionMessage(
        `❌ Replay failed: ${e.message ?? "Unknown error"} (check logs)`
      );
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            Delivery Replay
          </h2>
          <p className="text-xs text-slate-500">
            Retry failed/pending alert deliveries from Command Center.
          </p>
        </div>
        {loading ? (
          <span className="text-xs text-slate-400">Loading…</span>
        ) : null}
      </div>

      {error ? (
        <div className="text-sm text-red-500 bg-red-50 border border-red-100 rounded-lg p-2">
          {error}
        </div>
      ) : null}

      {actionMessage ? (
        <div className="text-xs text-slate-700 bg-slate-50 border border-slate-100 rounded-lg p-2">
          {actionMessage}
        </div>
      ) : null}

      <div className="flex flex-col gap-2 max-h-64 overflow-y-auto">
        {items.map((item) => {
          const statusBadgeClass =
            item.status === "delivered"
              ? "bg-emerald-100 text-emerald-800"
              : item.status === "failed"
              ? "bg-red-100 text-red-800"
              : item.status === "dead_letter"
              ? "bg-rose-100 text-rose-800"
              : "bg-amber-100 text-amber-800";

          return (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 border border-slate-100 rounded-xl px-3 py-2 hover:border-slate-200 transition"
            >
              <div className="flex flex-col flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">
                    {item.rule_name || "Unknown Rule"}
                  </span>
                  <span
                    className={`text-[10px] font-medium px-2 py-0.5 rounded ${statusBadgeClass}`}
                  >
                    {item.status}
                  </span>
                </div>
                <span className="text-xs text-slate-400 truncate">
                  {item.event_type} • {item.tenant_id || "—"}
                </span>
                {item.last_error && item.status !== "delivered" ? (
                  <span
                    className="text-[10px] text-red-600 truncate"
                    title={item.last_error}
                  >
                    {item.last_error.slice(0, 50)}...
                  </span>
                ) : null}
                <span className="text-[10px] text-slate-400">
                  Attempts: {item.attempts || 0}/{item.max_attempts || 5} •{" "}
                  {item.created_at
                    ? new Date(item.created_at).toLocaleTimeString()
                    : ""}
                </span>
              </div>
              <button
                onClick={() => handleReplay(item.id)}
                disabled={item.status === "delivered"}
                className={`text-xs font-medium px-3 py-1.5 rounded-lg whitespace-nowrap ${
                  item.status === "delivered"
                    ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                    : "bg-slate-900 text-white hover:bg-slate-800 transition"
                }`}
              >
                {item.status === "delivered" ? "✓ Done" : "🔄 Replay"}
              </button>
            </div>
          );
        })}
        {!loading && items.length === 0 ? (
          <div className="text-xs text-slate-400 text-center py-4">
            No recent deliveries found.
          </div>
        ) : null}
      </div>

      <div className="text-[10px] text-slate-400 border-t border-slate-100 pt-2">
        Showing last 10 deliveries • Auto-refresh every 30s
      </div>
    </div>
  );
};
