// ui/src/components/AutonomousActionsDashboard.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { TrendingUp, TrendingDown, Activity, Brain, Target, AlertTriangle } from 'lucide-react';

interface LearningInsights {
    learning_summary: {
        total_alert_types: number;
        total_actions: number;
        total_auto_actions: number;
        overall_success_rate: number;
        auto_success_rate: number;
        alert_type_breakdown: Record<string, {
            total_actions: number;
            success_rate: number;
            auto_success_rate: number;
            current_threshold: number;
            positive_feedback: number;
            negative_feedback: number;
            success_rates: {
                '1h': number;
                '24h': number;
                '7d': number;
            };
        }>;
    };
    dynamic_thresholds: Record<string, number>;
    recommendations: string[];
}

interface AutonomousActionsDashboardProps {
    tenant?: string;
}

export const AutonomousActionsDashboard: React.FC<AutonomousActionsDashboardProps> = ({ tenant }) => {
    const [insights, setInsights] = useState<LearningInsights | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchInsights();
        // Refresh every 30 seconds
        const interval = setInterval(fetchInsights, 30000);
        return () => clearInterval(interval);
    }, [tenant]);

    const fetchInsights = async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams();
            if (tenant) params.set('tenant', tenant);

            const response = await fetch(`/ops/adaptive/recommendations?${params}`);
            if (!response.ok) throw new Error('Failed to fetch insights');

            const data = await response.json();
            if (data.ok && data.learning_insights) {
                setInsights(data.learning_insights);
            } else {
                setInsights(null);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Brain className="h-5 w-5" />
                        Autonomous Actions Dashboard
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-4">
                        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                        <div className="h-4 bg-gray-200 rounded w-2/3"></div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error || !insights) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Brain className="h-5 w-5" />
                        Autonomous Actions Dashboard
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-center text-gray-500">
                        <AlertTriangle className="h-8 w-8 mx-auto mb-2" />
                        {error || 'No learning data available yet'}
                    </div>
                </CardContent>
            </Card>
        );
    }

    const { learning_summary } = insights;

    return (
        <div className="space-y-6">
            {/* Overview Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-600">Total Actions</p>
                                <p className="text-2xl font-bold">{learning_summary.total_actions}</p>
                            </div>
                            <Activity className="h-8 w-8 text-blue-500" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-600">Auto Actions</p>
                                <p className="text-2xl font-bold">{learning_summary.total_auto_actions}</p>
                            </div>
                            <Brain className="h-8 w-8 text-purple-500" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-600">Success Rate</p>
                                <p className="text-2xl font-bold">{(learning_summary.overall_success_rate * 100).toFixed(1)}%</p>
                                <div className="flex items-center mt-1">
                                    {learning_summary.overall_success_rate > 0.8 ? (
                                        <TrendingUp className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <TrendingDown className="h-4 w-4 text-red-500" />
                                    )}
                                </div>
                            </div>
                            <Target className="h-8 w-8 text-green-500" />
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-gray-600">Auto Success Rate</p>
                                <p className="text-2xl font-bold">{(learning_summary.auto_success_rate * 100).toFixed(1)}%</p>
                                <div className="flex items-center mt-1">
                                    {learning_summary.auto_success_rate > 0.8 ? (
                                        <TrendingUp className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <TrendingDown className="h-4 w-4 text-red-500" />
                                    )}
                                </div>
                            </div>
                            <Brain className="h-8 w-8 text-purple-500" />
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Alert Type Performance */}
            <Card>
                <CardHeader>
                    <CardTitle>Alert Type Performance</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        {Object.entries(learning_summary.alert_type_breakdown).map(([alertType, perf]) => (
                            <div key={alertType} className="border rounded-lg p-4">
                                <div className="flex items-center justify-between mb-2">
                                    <h3 className="font-medium">{alertType}</h3>
                                    <div className="flex items-center gap-2">
                                        <Badge variant={perf.current_threshold > 0.8 ? "secondary" : "default"}>
                                            Threshold: {(perf.current_threshold * 100).toFixed(1)}%
                                        </Badge>
                                        <Badge variant={perf.auto_success_rate > 0.8 ? "default" : "destructive"}>
                                            Auto: {(perf.auto_success_rate * 100).toFixed(1)}%
                                        </Badge>
                                    </div>
                                </div>

                                <div className="grid grid-cols-3 gap-4 mb-2">
                                    <div>
                                        <p className="text-sm text-gray-600">Total Actions</p>
                                        <p className="font-medium">{perf.total_actions}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-600">Success Rate</p>
                                        <p className="font-medium">{(perf.success_rate * 100).toFixed(1)}%</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-gray-600">Feedback</p>
                                        <p className="font-medium">
                                            +{perf.positive_feedback} / -{perf.negative_feedback}
                                        </p>
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>1h Success Rate</span>
                                            <span>{(perf.success_rates['1h'] * 100).toFixed(1)}%</span>
                                        </div>
                                        <Progress value={perf.success_rates['1h'] * 100} className="h-2" />
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>24h Success Rate</span>
                                            <span>{(perf.success_rates['24h'] * 100).toFixed(1)}%</span>
                                        </div>
                                        <Progress value={perf.success_rates['24h'] * 100} className="h-2" />
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>7d Success Rate</span>
                                            <span>{(perf.success_rates['7d'] * 100).toFixed(1)}%</span>
                                        </div>
                                        <Progress value={perf.success_rates['7d'] * 100} className="h-2" />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Learning Recommendations */}
            {insights.recommendations.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle>AI Learning Recommendations</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-2">
                            {insights.recommendations.map((rec, idx) => (
                                <li key={idx} className="flex items-start gap-2">
                                    <Brain className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                    <span className="text-sm">{rec}</span>
                                </li>
                            ))}
                        </ul>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};
