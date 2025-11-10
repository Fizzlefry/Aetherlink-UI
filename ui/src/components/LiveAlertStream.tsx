import * as React from "react";

type Alert = {
    id: string;
    severity: "info" | "warning" | "error" | "critical";
    title: string;
    message: string;
    source: string;
    tenant?: string;
    ts_iso: string;
    ack?: boolean;
    ack_by?: string;
};

interface LiveAlertStreamProps {
    alerts: Alert[];
    tenant?: string | null;
}

export function LiveAlertStream({ alerts, tenant }: LiveAlertStreamProps) {
    const [filteredAlerts, setFilteredAlerts] = React.useState<Alert[]>([]);
    const [loading, setLoading] = React.useState<string | null>(null);

    const acknowledgeAlert = async (alertId: string) => {
        setLoading(alertId);
        try {
            const response = await fetch(`/ui/alerts/${alertId}/ack`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-api-key': localStorage.getItem('apiKey') || '',
                    'x-admin-key': localStorage.getItem('adminKey') || '',
                },
            });
            if (!response.ok) {
                throw new Error('Failed to acknowledge alert');
            }
            // Refresh the alerts by triggering a re-render
            window.location.reload();
        } catch (error) {
            console.error('Error acknowledging alert:', error);
            alert('Failed to acknowledge alert');
        } finally {
            setLoading(null);
        }
    };

    const unacknowledgeAlert = async (alertId: string) => {
        setLoading(alertId);
        try {
            const response = await fetch(`/ui/alerts/${alertId}/unack`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-api-key': localStorage.getItem('apiKey') || '',
                    'x-admin-key': localStorage.getItem('adminKey') || '',
                },
            });
            if (!response.ok) {
                throw new Error('Failed to unacknowledge alert');
            }
            // Refresh the alerts by triggering a re-render
            window.location.reload();
        } catch (error) {
            console.error('Error unacknowledging alert:', error);
            alert('Failed to unacknowledge alert');
        } finally {
            setLoading(null);
        }
    };

    React.useEffect(() => {
        // Filter alerts by tenant if specified, and sort by timestamp descending
        const filtered = alerts
            .filter(alert => !tenant || alert.tenant === tenant)
            .sort((a, b) => new Date(b.ts_iso).getTime() - new Date(a.ts_iso).getTime())
            .slice(0, 10); // Show latest 10

        setFilteredAlerts(filtered);
    }, [alerts, tenant]);

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case "critical": return "bg-red-500/20 text-red-100 border-red-500/30";
            case "error": return "bg-red-400/20 text-red-100 border-red-400/30";
            case "warning": return "bg-amber-500/20 text-amber-100 border-amber-500/30";
            case "info": return "bg-blue-500/20 text-blue-100 border-blue-500/30";
            default: return "bg-slate-600/50 text-slate-100 border-slate-600/30";
        }
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case "critical": return "🚨";
            case "error": return "❌";
            case "warning": return "⚠️";
            case "info": return "ℹ️";
            default: return "📢";
        }
    };

    return (
        <div className="rounded-xl bg-slate-900/40 border border-slate-700 p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
                <h2 className="text-slate-100 font-semibold text-sm">
                    Live Alert Stream
                </h2>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
                    <span className="text-xs text-slate-400">Live</span>
                </div>
            </div>

            {filteredAlerts.length === 0 ? (
                <p className="text-slate-500 text-sm">
                    No alerts{tenant ? ` for ${tenant}` : ""} at this time.
                </p>
            ) : (
                <ul className="flex flex-col gap-2">
                    {filteredAlerts.map((alert) => {
                        const ts = new Date(alert.ts_iso).toLocaleString();
                        const isAcknowledged = alert.ack;

                        return (
                            <li
                                key={alert.id}
                                className={`flex items-start gap-3 p-3 rounded-lg border ${getSeverityColor(alert.severity)} ${isAcknowledged ? 'opacity-60' : ''
                                    }`}
                            >
                                <div className="flex-shrink-0 mt-0.5">
                                    <span className="text-sm">{getSeverityIcon(alert.severity)}</span>
                                </div>
                                <div className="flex flex-col gap-1 flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs uppercase tracking-wide font-medium">
                                            {alert.severity}
                                        </span>
                                        {tenant ? (
                                            <span className="text-xs text-slate-400">
                                                {tenant}
                                            </span>
                                        ) : alert.tenant ? (
                                            <span className="text-xs text-slate-400">
                                                {alert.tenant}
                                            </span>
                                        ) : null}
                                        {isAcknowledged && (
                                            <span className="text-xs text-slate-500">
                                                ✓ ACK
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-sm text-slate-100 font-medium">
                                        {alert.title}
                                    </p>
                                    <p className="text-sm text-slate-300">
                                        {alert.message}
                                    </p>
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-xs text-slate-500">
                                            {ts} • {alert.source}
                                        </p>
                                        <div className="flex items-center gap-1">
                                            {isAcknowledged && alert.ack_by && (
                                                <span className="text-xs text-slate-500">
                                                    by {alert.ack_by}
                                                </span>
                                            )}
                                            {isAcknowledged ? (
                                                <button
                                                    onClick={() => unacknowledgeAlert(alert.id)}
                                                    disabled={loading === alert.id}
                                                    className="px-2 py-1 text-xs bg-slate-600 hover:bg-slate-500 disabled:opacity-50 text-slate-200 rounded"
                                                >
                                                    {loading === alert.id ? '...' : 'Unack'}
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => acknowledgeAlert(alert.id)}
                                                    disabled={loading === alert.id}
                                                    className="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded"
                                                >
                                                    {loading === alert.id ? '...' : 'Ack'}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}
