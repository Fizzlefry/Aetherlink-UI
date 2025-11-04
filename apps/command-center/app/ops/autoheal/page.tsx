// apps/command-center/app/ops/autoheal/page.tsx
"use client";
import { useEffect, useRef, useState } from "react";

type Ev = { ts?: number; kind?: string; alertname?: string; msg?: string };

export default function AutohealOps() {
    const [events, setEvents] = useState<Ev[]>([]);
    const filterRef = useRef<HTMLInputElement>(null);
    const [status, setStatus] = useState<"connecting" | "live" | "down">("connecting");

    useEffect(() => {
        const es = new EventSource("/api/ops/autoheal/events"); // proxy to PeakPro API → Autoheal
        es.onopen = () => setStatus("live");
        es.onerror = () => setStatus("down");
        es.onmessage = e => {
            try {
                const ev = JSON.parse(e.data);
                setEvents(prev => [ev, ...prev].slice(0, 500));
            } catch { }
        };
        return () => es.close();
    }, []);

    const passFilter = (ev: Ev) => {
        const q = (filterRef.current?.value || "").trim().toLowerCase();
        if (!q) return true;
        const text = JSON.stringify(ev).toLowerCase();
        const ors = q.split(/\s+or\s+/);
        return ors.some(block =>
            block.split(/\s+/).every(tok => {
                if (!tok) return true;
                const kv = tok.split("=");
                if (kv.length === 2) {
                    const k = kv[0]; const v = kv[1];
                    // @ts-ignore
                    return String(ev?.[k] ?? "").toLowerCase().includes(v);
                }
                return text.includes(tok);
            })
        );
    };

    return (
        <div className="min-h-screen bg-[#0b0f14] text-[#eef]">
            <header className="p-4 border-b border-[#223] flex items-center gap-3">
                <h1 className="text-xl font-semibold">Autoheal · Live Events</h1>
                <span className={`px-2 py-0.5 rounded-full text-sm border ${status === "live" ? "border-green-500 text-green-500" : "border-yellow-500 text-yellow-500"}`}>
                    {status}
                </span>
                <div className="ml-auto flex items-center gap-2">
                    <span className="opacity-75">Filter</span>
                    <input
                        ref={filterRef}
                        placeholder="kind=action_fail OR alertname=HighCPU"
                        className="bg-[#0b1120] border border-[#223] rounded-md px-2 py-1 text-sm w-[420px] focus:outline-none focus:border-[#4a90e2]"
                        onChange={() => setEvents(evts => [...evts])}
                    />
                </div>
            </header>

            <section className="p-4 grid gap-3">
                <div className="grid grid-cols-3 gap-3">
                    <a
                        className="block border border-[#223] rounded-xl p-4 hover:bg-[#0f1620] transition-colors cursor-pointer"
                        href="/api/ops/autoheal/audit?n=200"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        <div className="text-sm opacity-80">Audit Trail</div>
                        <div className="text-lg font-medium">Last 200 Events</div>
                    </a>
                    <a
                        className="block border border-[#223] rounded-xl p-4 hover:bg-[#0f1620] transition-colors cursor-pointer"
                        href="http://localhost:3000/d/AETHERLINK_AUTOHEAL"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        <div className="text-sm opacity-80">Grafana Dashboard</div>
                        <div className="text-lg font-medium">Autoheal Metrics</div>
                    </a>
                    <a
                        className="block border border-[#223] rounded-xl p-4 hover:bg-[#0f1620] transition-colors cursor-pointer"
                        href="/api/ops/autoheal/healthz"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        <div className="text-sm opacity-80">Service Health</div>
                        <div className="text-lg font-medium">Health Check</div>
                    </a>
                </div>

                <div className="grid gap-2">
                    {events.filter(passFilter).length === 0 && (
                        <div className="text-center py-8 opacity-50">
                            {events.length === 0 ? "Waiting for events..." : "No events match filter"}
                        </div>
                    )}
                    {events.filter(passFilter).map((ev, idx) => (
                        <div key={idx} className="grid grid-cols-[140px_200px_1fr] gap-3 bg-[#0f1620] border border-[#223] rounded-xl p-3 hover:border-[#334] transition-colors">
                            <span className={`px-2 py-0.5 rounded-full border text-xs inline-block text-center ${ev.kind?.includes('fail') || ev.kind?.includes('error')
                                    ? 'border-red-500/50 bg-red-500/10 text-red-400'
                                    : ev.kind?.includes('ok') || ev.kind?.includes('executed')
                                        ? 'border-green-500/50 bg-green-500/10 text-green-400'
                                        : ev.kind?.includes('dry_run')
                                            ? 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400'
                                            : 'border-[#2a3b55] bg-[#182230] text-[#8ba]'
                                }`}>
                                {ev.kind ?? "—"}
                            </span>
                            <span className="opacity-80 text-sm">
                                {ev.ts ? new Date(ev.ts * 1000).toLocaleString() : "—"}
                            </span>
                            <div className="font-mono text-sm">
                                {ev.alertname && <span className="text-[#4a90e2] font-medium">{ev.alertname}</span>}
                                {ev.msg && <span className="ml-2 opacity-90">{ev.msg}</span>}
                            </div>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}
