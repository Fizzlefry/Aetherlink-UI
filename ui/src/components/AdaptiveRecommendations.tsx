import * as React from "react";

interface AdaptiveRecommendationsProps {
    tenant?: string | null;
}

export function AdaptiveRecommendations({ tenant }: AdaptiveRecommendationsProps) {
    const [data, setData] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        const fetchRecommendations = async () => {
            try {
                const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
                const response = await fetch(`/ops/adaptive/recommendations${qs}`);
                if (response.ok) {
                    const result = await response.json();
                    setData(result);
                } else {
                    console.error('Failed to fetch recommendations');
                    setData(null);
                }
            } catch (error) {
                console.error('Error fetching recommendations:', error);
                setData(null);
            } finally {
                setLoading(false);
            }
        };

        fetchRecommendations();
    }, [tenant]);

    const submitFeedback = async (type: string, target: string, feedback: string) => {
        try {
            await fetch('/ops/adaptive/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type,
                    target,
                    feedback,
                    tenant: tenant || undefined,
                }),
            });
        } catch (error) {
            console.error('Error submitting feedback:', error);
        }
    };

    const applyAutoAck = async (alertId: string) => {
        try {
            const response = await fetch('/ops/adaptive/apply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: 'auto_ack_candidate',
                    alert_id: alertId,
                    tenant: tenant || 'system',
                }),
            });
            if (response.ok) {
                // Refresh recommendations after applying
                const qs = tenant ? `?tenant=${encodeURIComponent(tenant)}` : "";
                const refreshResponse = await fetch(`/ops/adaptive/recommendations${qs}`);
                if (refreshResponse.ok) {
                    const result = await refreshResponse.json();
                    setData(result);
                }
            } else {
                console.error('Failed to apply auto-ack');
            }
        } catch (error) {
            console.error('Error applying auto-ack:', error);
        }
    };

    if (loading) {
        return (
            <div className="rounded-xl bg-slate-900/40 border border-slate-700 p-4">
                <div className="text-slate-400 text-sm">Loading recommendations...</div>
            </div>
        );
    }

    if (!data || !data.ok) {
        return (
            <div className="rounded-xl bg-slate-900/40 border border-slate-700 p-4">
                <div className="text-slate-400 text-sm">Adaptive recommendations unavailable</div>
            </div>
        );
    }

    return (
        <div className="rounded-xl bg-slate-900/40 border border-slate-700 p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
                <h2 className="text-slate-100 font-semibold text-sm">
                    Adaptive Recommendations
                </h2>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse"></div>
                    <span className="text-xs text-slate-400">AI</span>
                </div>
            </div>

            <p className="text-xs text-slate-500 mb-2">
                Window: last {data.window_hours}h • {data.total_events_analyzed} events analyzed
            </p>

            {/* Top Operator Actions */}
            <div className="space-y-2">
                <h3 className="text-xs text-slate-400 uppercase tracking-wide">Top Operator Actions</h3>
                {(data.top_operator_actions ?? []).slice(0, 5).map((item: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 p-2 rounded bg-slate-800/50">
                        <div className="flex-1">
                            <div className="text-xs uppercase tracking-wide font-medium text-slate-200">
                                {item.operation}
                            </div>
                            <div className="text-[11px] text-slate-400 mt-1">
                                seen {item.count} times • {item.recommendation}
                            </div>
                        </div>
                        <div className="flex gap-1">
                            <button
                                onClick={() => submitFeedback('action_recommendation', item.operation, 'good')}
                                className="px-1.5 py-0.5 text-[10px] bg-green-600/20 hover:bg-green-600/30 text-green-300 rounded"
                            >
                                👍
                            </button>
                            <button
                                onClick={() => submitFeedback('action_recommendation', item.operation, 'bad')}
                                className="px-1.5 py-0.5 text-[10px] bg-red-600/20 hover:bg-red-600/30 text-red-300 rounded"
                            >
                                👎
                            </button>
                        </div>
                    </div>
                ))}
                {(!data.top_operator_actions || data.top_operator_actions.length === 0) && (
                    <div className="text-xs text-slate-500 italic">
                        No operator actions in analysis window
                    </div>
                )}
            </div>

            {/* Auto-ack Candidates */}
            {data.auto_ack_candidates?.length ? (
                <div className="space-y-2">
                    <h3 className="text-xs text-slate-400 uppercase tracking-wide">Auto-ack Candidates</h3>
                    {data.auto_ack_candidates.map((cand: any, i: number) => (
                        <div key={i} className="flex items-start gap-2 p-2 rounded bg-blue-900/20 border border-blue-700/30">
                            <div className="flex-1">
                                <div className="text-xs font-medium text-blue-200">
                                    {cand.alert_id}
                                </div>
                                <div className="text-[11px] text-blue-300/70 mt-1">
                                    {Math.round(cand.confidence * 100)}% confidence • {cand.reason}
                                </div>
                            </div>
                            <div className="flex gap-1">
                                <button
                                    onClick={() => applyAutoAck(cand.alert_id)}
                                    className="px-2 py-1 text-[10px] bg-blue-600 hover:bg-blue-700 text-white rounded font-medium"
                                >
                                    Apply
                                </button>
                                <button
                                    onClick={() => submitFeedback('auto_ack_candidate', cand.alert_id, 'good')}
                                    className="px-1.5 py-0.5 text-[10px] bg-green-600/20 hover:bg-green-600/30 text-green-300 rounded"
                                >
                                    👍
                                </button>
                                <button
                                    onClick={() => submitFeedback('auto_ack_candidate', cand.alert_id, 'bad')}
                                    className="px-1.5 py-0.5 text-[10px] bg-red-600/20 hover:bg-red-600/30 text-red-300 rounded"
                                >
                                    👎
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            ) : null}
        </div>
    );
}
