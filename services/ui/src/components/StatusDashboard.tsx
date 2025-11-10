// src/components/StatusDashboard.tsx
import { useEffect, useState } from "react";

type ServiceStatus = {
    name: string;
    up: boolean;
    last_value: number;
};

type StatusSummary = {
    env: string;
    services: ServiceStatus[];
    alerts: {
        total: number;
        firing: number;
        warning: number;
        critical: number;
    };
    timestamp: number;
};

export function StatusDashboard() {
    const [data, setData] = useState<StatusSummary | null>(null);
    const [env, setEnv] = useState("local");
    const [loading, setLoading] = useState(true);

    const load = async (envVal = env) => {
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8010/status/summary?env=${encodeURIComponent(envVal)}`);
            const json = await res.json();
            setData(json);
        } catch (error) {
            console.error("Failed to load status:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load(env);
    }, [env]);

    if (loading || !data) {
        return <div className="p-4 text-sm text-slate-400">Loading status…</div>;
    }

    return (
        <div className="p-4 flex flex-col gap-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-slate-100">
                        AetherLink – System Status
                    </h2>
                    <p className="text-xs text-slate-400">
                        Env: {data.env} · Updated:{" "}
                        {new Date(data.timestamp * 1000).toLocaleTimeString()}
                    </p>
                </div>
                <div className="flex gap-2 items-center">
                    <label htmlFor="env-select" className="text-xs text-slate-300">Env</label>
                    <select
                        id="env-select"
                        value={env}
                        onChange={(e) => setEnv(e.target.value)}
                        className="bg-slate-800 text-slate-100 text-xs rounded px-2 py-1 border border-slate-700"
                    >
                        <option value="local">local</option>
                        <option value="dev">dev</option>
                        <option value="prod">prod</option>
                    </select>
                </div>
            </div>

            {/* Alerts bar */}
            <div className="grid grid-cols-4 gap-3">
                <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800">
                    <p className="text-xs text-slate-400">Total Alerts</p>
                    <p className="text-2xl font-semibold text-slate-50">
                        {data.alerts.total}
                    </p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800">
                    <p className="text-xs text-slate-400">Firing</p>
                    <p className="text-2xl font-semibold text-amber-300">
                        {data.alerts.firing}
                    </p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800">
                    <p className="text-xs text-slate-400">Warning</p>
                    <p className="text-2xl font-semibold text-yellow-200">
                        {data.alerts.warning}
                    </p>
                </div>
                <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800">
                    <p className="text-xs text-slate-400">Critical</p>
                    <p className="text-2xl font-semibold text-red-300">
                        {data.alerts.critical}
                    </p>
                </div>
            </div>

            {/* Services grid */}
            <div>
                <h3 className="text-sm text-slate-200 mb-2">Services</h3>
                <div className="grid lg:grid-cols-4 md:grid-cols-3 grid-cols-2 gap-3">
                    {data.services.map((svc) => (
                        <div
                            key={svc.name}
                            className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 flex items-center justify-between"
                        >
                            <div>
                                <p className="text-sm text-slate-100">{svc.name}</p>
                                <p className="text-[10px] text-slate-500">
                                    last={svc.last_value}
                                </p>
                            </div>
                            <div
                                className={`w-2.5 h-2.5 rounded-full ${svc.up ? "bg-emerald-400" : "bg-red-400"
                                    }`}
                                title={svc.up ? "Up" : "Down"}
                            />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
