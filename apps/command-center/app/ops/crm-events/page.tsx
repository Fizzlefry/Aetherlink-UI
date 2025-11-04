"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Evt = { ts?: string } & Record<string, any>;

export default function CrmEventsPage() {
    const [events, setEvents] = useState<Evt[]>([]);
    const [paused, setPaused] = useState(false);
    const [filter, setFilter] = useState("");
    const [status, setStatus] = useState<"idle" | "open" | "closed" | "error">("idle");
    const sourceRef = useRef<EventSource | null>(null);

    useEffect(() => {
        if (paused) {
            sourceRef.current?.close();
            setStatus("closed");
            return;
        }
        const sse = new EventSource("/api/ops/crm-events");
        sourceRef.current = sse;
        setStatus("open");

        sse.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                setEvents((prev) => {
                    const next = prev.concat([{ ...data, ts: new Date().toISOString() }]);
                    // cap list to avoid memory blow-up
                    if (next.length > 1000) next.shift();
                    return next;
                });
            } catch { }
        };
        sse.onerror = () => {
            setStatus("error");
            sse.close();
        };
        return () => sse.close();
    }, [paused]);

    const filtered = useMemo(() => {
        if (!filter.trim()) return events;
        const q = filter.toLowerCase();
        return events.filter((e) => JSON.stringify(e).toLowerCase().includes(q));
    }, [events, filter]);

    const download = () => {
        const blob = new Blob(
            filtered.map((e) => JSON.stringify(e) + "\n"),
            { type: "application/jsonl" } as any
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = `crm-events_${Date.now()}.jsonl`;
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="p-6 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm px-2 py-1 rounded bg-gray-800 text-white">
                    Status: {status}
                </span>
                <button
                    onClick={() => setPaused((p) => !p)}
                    className="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
                >
                    {paused ? "Resume" : "Pause"}
                </button>
                <button
                    onClick={() => setEvents([])}
                    className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300"
                >
                    Clear
                </button>
                <button
                    onClick={download}
                    className="px-3 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700"
                >
                    Download JSONL
                </button>
                <input
                    placeholder="Filter (e.g. JobCreated, TenantId, etc.)"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="px-3 py-1 rounded border w-96"
                />
                <span className="text-sm text-gray-500">
                    Showing {filtered.length} / {events.length}
                </span>
            </div>

            <div className="grid gap-2">
                {filtered.slice().reverse().map((e, i) => (
                    <pre
                        key={i}
                        className="text-xs p-3 rounded bg-black text-green-200 overflow-x-auto"
                    >
                        {JSON.stringify(e, null, 2)}
                    </pre>
                ))}
            </div>
        </div>
    );
}