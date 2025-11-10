import React, { useEffect, useState } from "react";
import { makeOperatorActivityWS } from "../lib/ws";

type ActivityItem = {
  path: string;
  method: string;
  status_code: number;
  ts: string;
  tenant?: string;
  actor?: string;
};

type OperatorActivityProps = {
  selectedTenant?: string;
};

export const OperatorActivity: React.FC<OperatorActivityProps> = ({
  selectedTenant,
}) => {
  const [items, setItems] = useState<ActivityItem[]>([]);

  useEffect(() => {
    const teardown = makeOperatorActivityWS((msg: { type?: string; payload?: ActivityItem }) => {
      if (msg?.type === "operator_activity" && msg.payload) {
        setItems((prev) => {
          const withNew = [msg.payload!, ...prev];
          // Keep last 25 items
          return withNew.slice(0, 25);
        });
      }
    });
    return teardown;
  }, []);

  // Filter by tenant if selected
  const filtered = selectedTenant && selectedTenant !== "all"
    ? items.filter((i) => i.tenant === selectedTenant)
    : items;

  return (
    <div style={{ marginTop: "2rem" }}>
      <div
        style={{
          background: "white",
          border: "1px solid #e5e7eb",
          borderRadius: "12px",
          padding: "1.25rem",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "1rem",
          }}
        >
          <h3 style={{ fontWeight: 600, fontSize: "0.875rem", color: "#374151" }}>
            👤 Operator Activity
          </h3>
          <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
            {filtered.length} event{filtered.length === 1 ? "" : "s"}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
            maxHeight: "300px",
            overflowY: "auto",
          }}
        >
          {filtered.length === 0 ? (
            <div
              style={{
                padding: "2rem",
                textAlign: "center",
                color: "#9ca3af",
                fontSize: "0.75rem",
              }}
            >
              No recent operator actions
            </div>
          ) : (
            filtered.map((item, idx) => {
              const timestamp = new Date(item.ts);
              const isError = item.status_code >= 400;

              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: isError ? "#fef2f2" : "#f9fafb",
                    border: `1px solid ${isError ? "#fca5a5" : "#e5e7eb"}`,
                    borderRadius: "6px",
                    padding: "0.5rem 0.75rem",
                    fontSize: "0.75rem",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isError ? "#fee2e2" : "#f3f4f6";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isError ? "#fef2f2" : "#f9fafb";
                  }}
                >
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    <div style={{ fontFamily: "monospace", fontSize: "0.7rem", color: "#374151" }}>
                      <span
                        style={{
                          fontWeight: 600,
                          color: item.method === "POST" ? "#3b82f6" : item.method === "DELETE" ? "#ef4444" : "#6b7280",
                        }}
                      >
                        {item.method}
                      </span>{" "}
                      {item.path}
                    </div>
                    <div style={{ fontSize: "0.65rem", color: "#9ca3af" }}>
                      {item.tenant ?? "no-tenant"} • {item.actor ?? "unknown"} •{" "}
                      {timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      padding: "0.125rem 0.5rem",
                      borderRadius: "4px",
                      fontWeight: 600,
                      background: isError ? "#fee2e2" : "#d1fae5",
                      color: isError ? "#991b1b" : "#065f46",
                    }}
                  >
                    {item.status_code}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
