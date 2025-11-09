import React, { useEffect, useState } from "react";
import toast, { Toaster } from "react-hot-toast";
import { useLocalStorage } from "../hooks/useLocalStorage";

type AetherEvent = {
    id: number;
    event_id: string;
    event_type: string;
    source: string;
    tenant_id?: string;
    severity?: string;
    timestamp: string;
    payload?: any;
    received_at: string;
    _meta?: {
        received_at: string;
        client_ip?: string;
    };
};

const showEventToast = (event: AetherEvent) => {
    const { event_type, payload, source } = event;

    let message = "";
    let type: "success" | "error" | "info" | "warning" = "info";

    switch (event_type) {
        case "delivery.replayed":
            message = `Delivery replayed: ${payload?.original_delivery_id || "unknown"} → ${payload?.new_delivery_id || "unknown"}`;
            type = "success";
            break;
        case "autoheal.cooldown.cleared":
            message = `Auto-heal cooldown cleared for ${payload?.endpoint || "endpoint"}`;
            type = "success";
            break;
        case "autoheal.attempted":
            message = `Auto-heal attempted: ${payload?.action || "unknown action"}`;
            type = "info";
            break;
        case "autoheal.succeeded":
            message = `Auto-heal succeeded: ${payload?.endpoint || "endpoint"} restored`;
            type = "success";
            break;
        case "autoheal.failed":
            message = `Auto-heal failed: ${payload?.endpoint || "endpoint"} - ${payload?.error || "unknown error"}`;
            type = "error";
            break;
        case "service.health.failed":
            message = `Service health failed: ${payload?.service || "unknown"} - ${payload?.reason || "check logs"}`;
            type = "error";
            break;
        case "service.registered":
            message = `Service registered: ${payload?.service || "unknown"}`;
            type = "info";
            break;
        case "ai.fallback.used":
            message = `AI fallback used: ${payload?.provider || "unknown"} → ${payload?.fallback || "unknown"}`;
            type = "warning";
            break;
        default:
            message = `${event_type}: ${source}`;
            type = "info";
    }

    // Show toast with appropriate styling
    switch (type) {
        case "success":
            toast.success(message, {
                duration: 4000,
                style: {
                    background: "#10b981",
                    color: "#fff",
                },
                icon: "✅",
            });
            break;
        case "error":
            toast.error(message, {
                duration: 6000,
                style: {
                    background: "#ef4444",
                    color: "#fff",
                },
                icon: "❌",
            });
            break;
        case "warning":
            toast(message, {
                duration: 5000,
                style: {
                    background: "#f59e0b",
                    color: "#fff",
                },
                icon: "⚠️",
            });
            break;
        default:
            toast(message, {
                duration: 4000,
                style: {
                    background: "#3b82f6",
                    color: "#fff",
                },
                icon: "ℹ️",
            });
    }
};

export const EventStream: React.FC<{ userRoles?: string }> = ({ userRoles = "operator" }) => {
    const [events, setEvents] = useState<AetherEvent[]>([]);
    const [connected, setConnected] = useState(false);
    const [filter, setFilter] = useLocalStorage<string>("cc.eventStream.filter", "all");
    const [severityFilter, setSeverityFilter] = useLocalStorage<string>("cc.eventStream.severityFilter", "all");
    const [tenant, setTenant] = useLocalStorage<string | null>("cc.eventStream.tenant", null);

    useEffect(() => {
        // Phase VII M3: Fetch recent events with optional tenant and severity filters
        const severityParam = severityFilter !== "all" ? `&severity=${severityFilter}` : "";
        const tenantParam = tenant ? `&tenant_id=${tenant}` : "";
        fetch(`http://localhost:8010/events/recent?limit=20${severityParam}${tenantParam}`, {
            headers: { "X-User-Roles": userRoles },
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.events) {
                    setEvents(data.events.reverse()); // Newest last for chronological display
                }
            })
            .catch((err) => console.warn("[EventStream] Failed to fetch recent:", err));

        // Connect to SSE stream
        const evtSrc = new EventSource("http://localhost:8010/events/stream");
        setConnected(true);

        evtSrc.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                setEvents((prev) => {
                    const next = [...prev, data];
                    // Keep last 50 events in memory
                    return next.slice(-50);
                });

                // Show toast notification for new events
                showEventToast(data);
            } catch (err) {
                console.warn("[EventStream] Bad event:", err);
            }
        };

        evtSrc.onerror = () => {
            console.warn("[EventStream] SSE connection error");
            setConnected(false);
            evtSrc.close();
        };

        return () => {
            evtSrc.close();
        };
    }, [severityFilter, tenant]); // Phase VII M3: Re-fetch when tenant or severity filter changes

    const getSeverityColor = (severity?: string) => {
        switch (severity) {
            case "critical":
                return "bg-red-100 text-red-800 border-red-300";
            case "error":
                return "bg-orange-100 text-orange-800 border-orange-300";
            case "warning":
                return "bg-yellow-100 text-yellow-800 border-yellow-300";
            case "info":
            default:
                return "bg-blue-100 text-blue-800 border-blue-300";
        }
    };

    const getEventTypeColor = (eventType: string) => {
        if (eventType.includes("autoheal")) return "text-purple-700";
        if (eventType.includes("ai.")) return "text-indigo-700";
        if (eventType.includes("service.")) return "text-green-700";
        if (eventType.includes("delivery")) return "text-orange-700";
        return "text-gray-700";
    };

    const filteredEvents = events.filter((evt) => {
        if (filter === "all") return true;
        if (filter === "autoheal") return evt.event_type.includes("autoheal");
        if (filter === "deliveries") return evt.event_type.includes("delivery");
        if (filter === "ai") return evt.event_type.includes("ai.");
        if (filter === "service") return evt.event_type.includes("service.");
        return true;
    });

    return (
        <>
            <div className="mt-6 border rounded-lg p-4 bg-white shadow-sm">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                        <h2 className="text-lg font-semibold">Live Event Stream</h2>
                        <span
                            className={`text-xs px-2 py-1 rounded font-medium ${connected ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                                }`}
                        >
                            {connected ? "● LIVE" : "○ DISCONNECTED"}
                        </span>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setFilter("all")}
                            className={`text-xs px-3 py-1 rounded ${filter === "all"
                                ? "bg-blue-600 text-white"
                                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                }`}
                        >
                            All ({events.length})
                        </button>
                        <button
                            onClick={() => setFilter("autoheal")}
                            className={`text-xs px-3 py-1 rounded ${filter === "autoheal"
                                ? "bg-purple-600 text-white"
                                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                }`}
                        >
                            Auto-Heal
                        </button>
                        <button
                            onClick={() => setFilter("deliveries")}
                            className={`text-xs px-3 py-1 rounded ${filter === "deliveries"
                                ? "bg-orange-600 text-white"
                                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                }`}
                        >
                            Deliveries
                        </button>
                        <button
                            onClick={() => setFilter("ai")}
                            className={`text-xs px-3 py-1 rounded ${filter === "ai"
                                ? "bg-indigo-600 text-white"
                                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                }`}
                        >
                            AI
                        </button>
                        <button
                            onClick={() => setFilter("service")}
                            className={`text-xs px-3 py-1 rounded ${filter === "service"
                                ? "bg-green-600 text-white"
                                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                                }`}
                        >
                            Services
                        </button>
                    </div>
                </div>

                {/* Phase VI M5: Severity Filter Row */}
                <div className="flex items-center gap-2 mb-3 text-xs">
                    <span className="text-gray-600 font-medium">Severity:</span>
                    <button
                        onClick={() => setSeverityFilter("all")}
                        className={`px-3 py-1 rounded ${severityFilter === "all"
                            ? "bg-gray-700 text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                    >
                        All
                    </button>
                    <button
                        onClick={() => setSeverityFilter("info")}
                        className={`px-3 py-1 rounded ${severityFilter === "info"
                            ? "bg-blue-600 text-white"
                            : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                            }`}
                    >
                        Info
                    </button>
                    <button
                        onClick={() => setSeverityFilter("warning")}
                        className={`px-3 py-1 rounded ${severityFilter === "warning"
                            ? "bg-yellow-600 text-white"
                            : "bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                            }`}
                    >
                        Warnings
                    </button>
                    <button
                        onClick={() => setSeverityFilter("error")}
                        className={`px-3 py-1 rounded ${severityFilter === "error"
                            ? "bg-orange-600 text-white"
                            : "bg-orange-100 text-orange-700 hover:bg-orange-200"
                            }`}
                    >
                        Errors
                    </button>
                    <button
                        onClick={() => setSeverityFilter("critical")}
                        className={`px-3 py-1 rounded ${severityFilter === "critical"
                            ? "bg-red-600 text-white"
                            : "bg-red-100 text-red-700 hover:bg-red-200"
                            }`}
                    >
                        Critical
                    </button>
                </div>

                {/* Phase VII M3: Tenant Filter Row */}
                <div className="flex items-center gap-2 mb-3 text-xs">
                    <span className="text-gray-600 font-medium">Tenant:</span>
                    <select
                        value={tenant ?? ""}
                        onChange={(e) => setTenant(e.target.value || null)}
                        className="px-3 py-1 rounded border border-gray-300 bg-white text-gray-700 hover:border-gray-400 focus:outline-none focus:border-blue-500"
                    >
                        <option value="">All tenants</option>
                        <option value="tenant-1">tenant-1</option>
                        <option value="tenant-2">tenant-2</option>
                        <option value="tenant-acme">tenant-acme</option>
                        <option value="tenant-demo">tenant-demo</option>
                    </select>
                </div>

                <div className="max-h-96 overflow-y-auto space-y-2 border-t pt-3">
                    {filteredEvents.length === 0 ? (
                        <div className="text-center py-8 text-gray-500">
                            <p className="text-sm">No events yet.</p>
                            <p className="text-xs mt-1">Events will appear here as they happen.</p>
                        </div>
                    ) : (
                        filteredEvents
                            .slice()
                            .reverse() // Newest first for display
                            .map((evt) => (
                                <div
                                    key={evt.id || evt.event_id}
                                    className={`border rounded p-3 text-sm ${getSeverityColor(evt.severity)}`}
                                >
                                    <div className="flex justify-between items-start">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span
                                                    className={`font-semibold text-xs ${getEventTypeColor(
                                                        evt.event_type
                                                    )}`}
                                                >
                                                    {evt.event_type}
                                                </span>
                                                {evt.severity && (
                                                    <span className="text-xs font-medium uppercase">
                                                        {evt.severity}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-xs text-gray-600 mb-2">
                                                <span className="font-mono">from: {evt.source}</span>
                                                {evt.tenant_id && evt.tenant_id !== "default" && (
                                                    <span className="ml-3">tenant: {evt.tenant_id}</span>
                                                )}
                                            </div>
                                            {evt.payload && Object.keys(evt.payload).length > 0 && (
                                                <details className="mt-2">
                                                    <summary className="cursor-pointer text-xs text-gray-600 hover:text-gray-800">
                                                        Show payload
                                                    </summary>
                                                    <pre className="text-xs bg-gray-50 mt-2 p-2 rounded overflow-x-auto border">
                                                        {JSON.stringify(evt.payload, null, 2)}
                                                    </pre>
                                                </details>
                                            )}
                                        </div>
                                        <div className="text-right ml-3">
                                            <div className="text-xs text-gray-500 font-mono">
                                                {new Date(evt.timestamp).toLocaleTimeString()}
                                            </div>
                                            <div className="text-xs text-gray-400 mt-1">
                                                {new Date(evt.received_at).toLocaleTimeString()}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))
                    )}
                </div>

                <div className="mt-3 text-xs text-gray-500 border-t pt-2">
                    <div className="flex justify-between">
                        <span>Showing {filteredEvents.length} events</span>
                        <span>Buffered in memory: last 50</span>
                    </div>
                </div>
            </div>
            <Toaster position="top-right" />
        </>
    );
};
