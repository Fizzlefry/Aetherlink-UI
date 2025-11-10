import { Link } from 'react-router-dom';
import { useEffect, useState } from "react";
import { LocalRunsCard } from "./components/LocalRunsCard";
import { LastAuditBadge } from "./components/LastAuditBadge";
import { api } from "./lib/api";
import { OpsMetricsCard } from "./components/OpsMetricsCard";
import { AnalyticsCard } from "./components/AnalyticsCard";
import { JobsControlCard } from "./components/JobsControlCard";
import { QueueStatusCard } from "./components/QueueStatusCard";
import { TenantScopeSelector } from "./components/TenantScopeSelector";
import { RecentOperatorActivity } from "./components/RecentOperatorActivity";
import { LiveAlertStream } from "./components/LiveAlertStream";
import { AdaptiveRecommendations } from "./components/AdaptiveRecommendations";
import { ICON_COMMAND_CENTER, ICON_CRM_DEFAULT, ICON_CRM_POLICY, ICON_CRM_HOME, ICON_CRM_CHAT } from "./icons";

interface BundleData {
    status: any;
    federation: any;
    opt: any;
    learn: any;
    policies: any;
    alerts: any[];
}

interface DashboardHomeProps {
    bundle: BundleData | null;
}

interface BackendInfo {
    service: string;
    version: string;
    features: Record<string, boolean>;
    endpoints: string[];
}

type ScheduleStatus = {
    ok: boolean;
    schedules: Record<string, unknown>;
};

function CommandCenterStatusCard() {
    const [status, setStatus] = useState<"loading" | "up" | "down">("loading");
    const [data, setData] = useState<ScheduleStatus | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();

        async function load() {
            try {
                const res = await api("/api/crm/import/acculynx/schedule/status", {
                    method: "GET",
                    signal: controller.signal,
                });

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const json = (await res.json()) as ScheduleStatus;
                setData(json);
                setStatus("up");
                setError(null);
            } catch (err: any) {
                setStatus("down");
                setError(err.message ?? "Failed to reach Command Center");
            }
        }

        load();

        // Poll every 30 seconds
        const id = setInterval(load, 30000);
        return () => {
            controller.abort();
            clearInterval(id);
        };
    }, []);

    if (status === "loading") {
        return (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-gray-400 animate-pulse"></div>
                    <span className="font-medium text-gray-900">Command Center</span>
                </div>
                <p className="text-sm text-gray-600">Checking status...</p>
            </div>
        );
    }

    if (status === "down") {
        return (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <span className="font-medium text-gray-900">Command Center</span>
                </div>
                <p className="text-sm text-gray-600">Offline</p>
                {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
            </div>
        );
    }

    return (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center space-x-2 mb-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="font-medium text-gray-900">Command Center</span>
            </div>
            <p className="text-sm text-gray-600">Online - {Object.keys(data?.schedules || {}).length} schedules</p>
        </div>
    );
}

function AIAutomationStatusCard() {
    const [status, setStatus] = useState<"loading" | "enabled" | "disabled" | "dry-run">("loading");
    const [config, setConfig] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();

        async function load() {
            try {
                const res = await api("/health/env", {
                    method: "GET",
                    signal: controller.signal,
                });

                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}`);
                }

                const json = await res.json();
                setConfig(json);

                // Determine status based on features
                const features = json.features || {};
                if (features.adaptive_dry_run) {
                    setStatus("dry-run");
                } else if (features.ai_guardrails && features.adaptive_auto_actions) {
                    setStatus("enabled");
                } else {
                    setStatus("disabled");
                }
                setError(null);
            } catch (err: any) {
                setStatus("disabled");
                setError(err.message ?? "Failed to check AI status");
            }
        }

        load();

        // Poll every 60 seconds (less frequent for config)
        const id = setInterval(load, 60000);
        return () => {
            controller.abort();
            clearInterval(id);
        };
    }, []);

    const getStatusColor = () => {
        switch (status) {
            case "enabled": return "bg-blue-500";
            case "dry-run": return "bg-yellow-500";
            case "disabled": return "bg-gray-500";
            default: return "bg-gray-400 animate-pulse";
        }
    };

    const getStatusText = () => {
        switch (status) {
            case "enabled": return "AI Automation: ACTIVE";
            case "dry-run": return "AI Automation: DRY-RUN";
            case "disabled": return "AI Automation: DISABLED";
            default: return "Checking AI status...";
        }
    };

    return (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center space-x-2 mb-2">
                <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
                <span className="font-medium text-gray-900">AI Automation</span>
            </div>
            <p className="text-sm text-gray-600">{getStatusText()}</p>
            {config && (
                <div className="text-xs text-gray-500 mt-1">
                    Guardrails: {config.features?.ai_guardrails ? "ENFORCED" : "OFF"} |
                    Environment: {config.environment?.toUpperCase()}
                </div>
            )}
            {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
    );
}

function SchedulerSummaryCard() {
    const [count, setCount] = useState<number | null>(null);
    const [ts, setTs] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                const res = await api("/api/crm/import/acculynx/schedule/status");
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const json = await res.json();
                if (cancelled) return;
                const schedules = json.schedules || {};
                setCount(Object.keys(schedules).length);
                setTs(json.ts_iso ?? null);
                setError(null);
            } catch (e: any) {
                if (cancelled) return;
                setError(e.message ?? "Failed to reach Command Center");
            }
        }

        load();
        const id = setInterval(load, 30000);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    if (error) {
        return (
            <div className="card p-4 bg-red-100 text-red-800">
                Command Center (AccuLynx scheduler) offline
                <div className="text-xs mt-1">{error}</div>
            </div>
        );
    }

    return (
        <div className="card p-4 bg-white shadow-sm rounded-lg">
            <div className="text-sm text-slate-500">AccuLynx Scheduler</div>
            <div className="text-2xl font-semibold">
                {count === null ? "..." : `${count} tenant${count === 1 ? "" : "s"}`}
            </div>
            <div className="text-xs text-slate-400 mt-1">
                {ts ? `as of ${ts}` : "checking..."}
            </div>
        </div>
    );
}

const UI_VERSION = "0.2.0";

function FooterStatus() {
    const [status, setStatus] = useState<"loading" | "connected" | "disconnected">("loading");

    useEffect(() => {
        let cancelled = false;

        async function ping() {
            try {
                await api("/ops/ping");
                if (!cancelled) setStatus("connected");
            } catch {
                if (!cancelled) setStatus("disconnected");
            }
        }

        ping();
        const id = setInterval(ping, 10000); // every 10s
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    return (
        <span className="ml-3 text-xs">
            {status === "connected" ? "online" : status === "disconnected" ? "offline" : "checking..."}
        </span>
    );
}


const crmVerticals = [
    {
        id: 'peakpro',
        name: 'PeakPro CRM',
        description: 'Roofing services and commercial inspections',
        icon: ICON_CRM_DEFAULT,
        path: '/peakpro',
        color: 'bg-blue-500',
        status: 'Active'
    },
    {
        id: 'policypal',
        name: 'PolicyPal CRM',
        description: 'Insurance claims and policy management',
        icon: ICON_CRM_POLICY,
        path: '/policypal',
        color: 'bg-green-500',
        status: 'Active'
    },
    {
        id: 'roofwonder',
        name: 'RoofWonder CRM',
        description: 'Residential roofing and maintenance',
        icon: ICON_CRM_HOME,
        path: '/roofwonder',
        color: 'bg-orange-500',
        status: 'Coming Soon'
    },
    {
        id: 'clientellme',
        name: 'Clientellme CRM',
        description: 'Client relationship management',
        icon: ICON_CRM_CHAT,
        path: '/clientellme',
        color: 'bg-purple-500',
        status: 'Coming Soon'
    },
    {
        id: 'apexflow',
        name: 'ApexFlow CRM',
        description: 'Construction project management',
        icon: ICON_CRM_DEFAULT,
        path: '/apexflow',
        color: 'bg-red-500',
        status: 'Coming Soon'
    }
];

export function DashboardHome({ bundle }: DashboardHomeProps) {
    const activeServices = bundle?.status?.services || [];
    const federationStatus = bundle?.federation?.status || 'unknown';
    const alertCount = bundle?.alerts?.length || 0;

    const [backendInfo, setBackendInfo] = useState<BackendInfo | null>(null);
    const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
    const [profile, setProfile] = useState<{ display_name: string; description: string } | null>(null);

    useEffect(() => {
        async function fetchBackendInfo() {
            try {
                const response = await fetch('http://localhost:8000/');
                if (response.ok) {
                    const data = await response.json();
                    setBackendInfo(data);
                }
            } catch (error) {
                console.warn('Failed to fetch backend info:', error);
            }
        }
        fetchBackendInfo();
    }, []);

    useEffect(() => {
        const currentTenant = selectedTenant ?? "GENERALDEMO";
        fetch(`/beta/profile?tenant=${encodeURIComponent(currentTenant)}`)
            .then(r => (r.ok ? r.json() : null))
            .then(data => data && setProfile(data))
            .catch(() => { });
    }, [selectedTenant]);

    return (
        <div className="min-h-screen bg-slate-50">
            {/* Header */}
            <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        <h1 className="text-2xl font-bold text-gray-900">AetherLink CRM Dashboard</h1>
                    </div>
                    <div className="flex items-center space-x-4">
                        {/* Federation Status */}
                        <div className="flex items-center space-x-2">
                            <div className={`w-2 h-2 rounded-full ${federationStatus === 'healthy' ? 'bg-green-500' :
                                federationStatus === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
                                }`}></div>
                            <span className="text-sm text-gray-600">
                                Federation: {federationStatus}
                            </span>
                        </div>
                        {/* Alert Count */}
                        {alertCount > 0 && (
                            <div className="flex items-center space-x-2">
                                <div className="w-2 h-2 rounded-full bg-red-500"></div>
                                <span className="text-sm text-gray-600">
                                    {alertCount} alert{alertCount !== 1 ? 's' : ''}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </header>

            {/* Profile Context Banner */}
            {profile ? (
                <div className="mb-3 rounded-lg bg-slate-900/40 border border-slate-800 px-4 py-2 mx-6">
                    <p className="text-xs text-slate-400">
                        Viewing demo data for <span className="text-slate-100">{profile.display_name}</span> — {profile.description}
                    </p>
                </div>
            ) : null}

            {/* Main Content */}
            <main className="px-6 py-8">
                <div className="max-w-7xl mx-auto">
                    {/* Welcome Section */}
                    <div className="mb-8">
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">
                            Welcome to AetherLink CRM
                        </h2>
                        <p className="text-gray-600">
                            Unified CRM interface across all AetherLink verticals. Select a CRM below to get started.
                        </p>
                    </div>

                    {/* Version Compatibility Banner */}
                    {backendInfo && backendInfo.version !== UI_VERSION && (
                        <div className="mb-6 bg-yellow-100 text-yellow-900 text-sm px-4 py-3 rounded-lg border border-yellow-200">
                            ⚠️ UI {UI_VERSION} ≠ API {backendInfo.version}. You may be talking to an older/newer Command Center.
                        </div>
                    )}

                    {/* Scheduler Summary & Local Runs & Ops Health */}
                    <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                        <SchedulerSummaryCard />
                        <LocalRunsCard />
                        <OpsMetricsCard />
                    </div>

                    {/* Analytics Snapshot */}
                    <div className="mb-8">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Analytics & Controls</h2>
                            <TenantScopeSelector
                                selectedTenant={selectedTenant}
                                onTenantChange={setSelectedTenant}
                            />
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <AnalyticsCard tenant={selectedTenant} />
                            <JobsControlCard tenant={selectedTenant} />
                            <QueueStatusCard tenant={selectedTenant} />
                        </div>
                    </div>

                    {/* Live Operations Stream */}
                    <div className="mb-8">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Live Operations Stream</h2>
                            <TenantScopeSelector
                                selectedTenant={selectedTenant}
                                onTenantChange={setSelectedTenant}
                            />
                        </div>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <RecentOperatorActivity tenant={selectedTenant} />
                            <LiveAlertStream alerts={bundle?.alerts || []} tenant={selectedTenant} />
                            <AdaptiveRecommendations tenant={selectedTenant} />
                        </div>
                    </div>

                    {/* Last Scheduler Activity */}
                    <div className="mb-8 p-4 bg-white shadow-sm rounded-lg border border-slate-200">
                        <div className="flex items-center justify-between mb-2">
                            <div className="text-sm font-medium text-slate-700">Last Scheduler Activity</div>
                            <div className="text-xs text-slate-400">auto-refresh 30s</div>
                        </div>
                        <LastAuditBadge />
                    </div>

                    {/* CRM Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {crmVerticals.map((vertical) => {
                            const isActive = activeServices.some((s: any) => s.name === vertical.id && s.up);
                            const isComingSoon = vertical.status === 'Coming Soon';

                            return (
                                <div
                                    key={vertical.id}
                                    className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow ${isComingSoon ? 'opacity-60' : ''
                                        }`}
                                >
                                    <div className="flex items-start justify-between mb-4">
                                        <div className={`w-12 h-12 rounded-lg ${vertical.color} flex items-center justify-center text-white text-xl`}>
                                            {vertical.icon}
                                        </div>
                                        <span className={`px-2 py-1 text-xs rounded-full ${vertical.status === 'Active'
                                            ? 'bg-green-100 text-green-800'
                                            : 'bg-gray-100 text-gray-600'
                                            }`}>
                                            {vertical.status}
                                        </span>
                                    </div>

                                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                                        {vertical.name}
                                    </h3>

                                    <p className="text-gray-600 text-sm mb-4">
                                        {vertical.description}
                                    </p>

                                    {/* Service Status */}
                                    <div className="flex items-center space-x-2 mb-4">
                                        <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'
                                            }`}></div>
                                        <span className="text-xs text-gray-500">
                                            {isActive ? 'Service Online' : 'Service Offline'}
                                        </span>
                                    </div>

                                    {/* Action Button */}
                                    {isComingSoon ? (
                                        <button
                                            disabled
                                            className="w-full bg-gray-100 text-gray-400 px-4 py-2 rounded-lg text-sm font-medium cursor-not-allowed"
                                        >
                                            Coming Soon
                                        </button>
                                    ) : (
                                        <Link
                                            to={vertical.path}
                                            className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium text-center block transition-colors"
                                        >
                                            Open CRM
                                        </Link>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* System Status Panel */}
                    <div className="mt-8 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4">
                            System Status
                        </h3>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {/* Federation Status */}
                            <div>
                                <div className="flex items-center space-x-2 mb-2">
                                    <div className={`w-3 h-3 rounded-full ${federationStatus === 'healthy' ? 'bg-green-500' :
                                        federationStatus === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'
                                        }`}></div>
                                    <span className="font-medium text-gray-900">Federation</span>
                                </div>
                                <p className="text-sm text-gray-600">
                                    {bundle?.federation?.peers_up || 0} of {bundle?.federation?.peers_total || 0} peers online
                                </p>
                            </div>

                            {/* Active Policies */}
                            <div>
                                <div className="flex items-center space-x-2 mb-2">
                                    <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                                    <span className="font-medium text-gray-900">Active Policies</span>
                                </div>
                                <p className="text-sm text-gray-600">
                                    {Object.keys(bundle?.policies?.active_policies || {}).length} policies applied
                                </p>
                            </div>

                            {/* Command Center Status */}
                            <CommandCenterStatusCard />

                            {/* AI Automation Status */}
                            <AIAutomationStatusCard />
                        </div>
                    </div>
                </div>
            </main>

            {/* Footer */}
            <footer className="bg-white border-t border-gray-200 px-6 py-4 mt-8">
                <div className="text-center text-sm text-gray-500 flex items-center justify-center">
                    {backendInfo ? (
                        <>{ICON_COMMAND_CENTER} Command Center v{backendInfo.version}</>
                    ) : (
                        <>{ICON_COMMAND_CENTER} Command Center</>
                    )}
                    <FooterStatus />
                </div>
            </footer>
        </div>
    );
}
