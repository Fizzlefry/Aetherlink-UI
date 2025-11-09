import { useState, useEffect } from 'react'
import { CrmShell, PipelineView, RecordView, AutomationsView } from '../crm-lib'
import { api } from '../lib/api'

interface BundleData {
    status: any;
    federation: any;
    opt: any;
    learn: any;
    policies: any;
    alerts: any[];
    tenant?: string;
    vertical?: string;
    customers?: any[];
    records?: any[];
    activities?: any[];
    files?: any[]; // Add files array
    last_synced_at?: number;
}

const AccuLynxSchedulePanel: React.FC = () => {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // Create schedule form state
    const [newTenant, setNewTenant] = useState<string>('');
    const [newInterval, setNewInterval] = useState<number>(180);
    const [createError, setCreateError] = useState<string | null>(null);
    const [creating, setCreating] = useState<boolean>(false);

    // Phase XIV: Track which tenant is running force-run
    const [runningTenant, setRunningTenant] = useState<string | null>(null);

    const fetchStatus = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('/api/crm/import/acculynx/schedule/status');
            const json = await res.json();
            setData(json);
        } catch (err: any) {
            setError(err.message || 'Failed to load scheduler status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();
        // refresh every 15s so you can watch last_run tick
        const id = setInterval(fetchStatus, 15000);
        return () => clearInterval(id);
    }, []);

    const schedules = data?.schedules || {};

    const formatTs = (ts?: number, isoTs?: string | null) => {
        // Prefer ISO timestamp if available (cleaner, mobile-friendly)
        if (isoTs) {
            return new Date(isoTs).toLocaleString();
        }
        if (!ts) return '—';
        return new Date(ts * 1000).toLocaleString();
    };

    const createSchedule = async () => {
        const normalizedTenant = newTenant.trim().toLowerCase();
        if (!normalizedTenant) {
            setCreateError('Tenant name is required');
            return;
        }
        setCreateError(null);
        setCreating(true);
        try {
            await api('/api/crm/import/acculynx/schedule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': normalizedTenant,
                },
                body: JSON.stringify({ interval_sec: newInterval }),
            });
            // Clear form and refresh
            setNewTenant('');
            setNewInterval(180);
            fetchStatus();
        } catch (err: any) {
            setCreateError(err.message || 'Failed to create schedule');
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="mt-4 p-3 border rounded bg-white shadow-sm space-y-2">
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">AccuLynx Auto-Sync Scheduler</h3>
                <button
                    onClick={fetchStatus}
                    className="px-2 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200"
                >
                    Refresh
                </button>
            </div>
            {loading && <p className="text-xs text-slate-400">Loading…</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}

            {/* Create Schedule Form */}
            <div className="border-b pb-2 mb-2">
                <p className="text-xs font-medium text-slate-600 mb-2">Create New Schedule</p>
                <div className="flex gap-2 items-start">
                    <div className="flex-1">
                        <input
                            type="text"
                            placeholder="tenant-slug"
                            value={newTenant}
                            onChange={(e) => setNewTenant(e.target.value)}
                            className="text-xs px-2 py-1 border rounded w-full"
                            aria-label="Tenant name"
                        />
                        <p className="text-[10px] text-slate-400 mt-1">lowercase, no spaces</p>
                    </div>
                    <select
                        value={newInterval}
                        onChange={(e) => setNewInterval(Number(e.target.value))}
                        className="text-xs px-2 py-1 border rounded"
                        aria-label="Sync interval"
                    >
                        <option value={60}>1 min</option>
                        <option value={180}>3 min</option>
                        <option value={300}>5 min</option>
                        <option value={600}>10 min</option>
                        <option value={900}>15 min</option>
                        <option value={1800}>30 min</option>
                    </select>
                    <button
                        type="button"
                        onClick={createSchedule}
                        disabled={creating}
                        className="text-xs px-3 py-1 rounded bg-green-100 hover:bg-green-200 text-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {creating ? 'Creating…' : 'Create'}
                    </button>
                </div>
                {createError && <p className="text-xs text-red-500 mt-1">{createError}</p>}
            </div>

            <div className="space-y-2 max-h-52 overflow-auto">
                {Object.keys(schedules).length === 0 && (
                    <p className="text-xs text-slate-400">No tenants scheduled yet. Use the Auto-sync buttons above to set a schedule.</p>
                )}
                {Object.entries(schedules).map(([tenant, cfg]: any) => {
                    const lastStatus = cfg.last_status || {};
                    const ok = lastStatus.ok !== false;
                    const paused = !!cfg.paused;
                    const nextRun = typeof cfg.next_run_in_sec === 'number'
                        ? Math.round(cfg.next_run_in_sec)
                        : null;

                    const pauseOrResume = async () => {
                        const endpoint = paused
                            ? '/api/crm/import/acculynx/resume'
                            : '/api/crm/import/acculynx/pause';
                        await fetch(endpoint, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'x-tenant': tenant,
                                'x-ops': '1',  // Phase XII: Mark as operator action
                            },
                        });
                        fetchStatus(); // Re-pull status
                    };

                    const runNow = async () => {
                        setRunningTenant(tenant);
                        try {
                            await api('/api/crm/import/acculynx/run-now', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'x-tenant': tenant,
                                },
                            });
                            fetchStatus(); // Re-pull status
                        } catch (err: any) {
                            alert(err.message || 'Failed to run now');
                        } finally {
                            setRunningTenant(null);
                        }
                    };

                    const deleteSchedule = async () => {
                        if (!confirm(`Delete schedule for ${tenant}?`)) return;
                        await fetch('/api/crm/import/acculynx/schedule', {
                            method: 'DELETE',
                            headers: {
                                'Content-Type': 'application/json',
                                'x-tenant': tenant,
                                'x-ops': '1',  // Phase XII: Mark as operator action
                            },
                        });
                        fetchStatus(); // Re-pull status
                    };

                    return (
                        <div
                            key={tenant}
                            className="flex items-start justify-between gap-2 border rounded p-2"
                        >
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium">{tenant}</span>
                                    <span
                                        className={
                                            'text-[10px] px-1 rounded ' +
                                            (paused
                                                ? 'bg-slate-200 text-slate-600'
                                                : ok
                                                    ? 'bg-green-100 text-green-700'
                                                    : 'bg-red-100 text-red-700')
                                        }
                                    >
                                        {paused ? 'PAUSED' : ok ? 'OK' : 'ERROR'}
                                    </span>
                                </div>
                                <p className="text-[11px] text-slate-500">
                                    Interval: {cfg.interval_sec}s ({Math.floor(cfg.interval_sec / 60)} min)
                                </p>
                                {!paused && nextRun !== null && (
                                    <p className="text-[11px] text-slate-500">
                                        Next run in: {nextRun}s
                                    </p>
                                )}
                                <p className="text-[11px] text-slate-500">
                                    Last run: {formatTs(cfg.last_run, cfg.last_run_iso)}
                                </p>
                                <p className="text-[11px] text-slate-400 mt-1">
                                    {lastStatus.message}
                                </p>
                            </div>
                            <div className="flex flex-col gap-1 items-end">
                                <div className="flex gap-1 flex-wrap justify-end">
                                    <button
                                        type="button"
                                        onClick={pauseOrResume}
                                        className="text-[10px] px-2 py-1 rounded bg-slate-100 hover:bg-slate-200"
                                    >
                                        {paused ? 'Resume' : 'Pause'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={runNow}
                                        disabled={runningTenant === tenant}
                                        className="text-[10px] px-2 py-1 rounded bg-blue-100 hover:bg-blue-200 text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {runningTenant === tenant ? 'Running…' : 'Run Now'}
                                    </button>
                                    <button
                                        type="button"
                                        onClick={deleteSchedule}
                                        className="text-[10px] px-2 py-1 rounded bg-red-100 hover:bg-red-200 text-red-700"
                                    >
                                        Delete
                                    </button>
                                </div>
                                {lastStatus.result?.stats && (
                                    <span className="text-[10px] text-slate-400">
                                        imported: {lastStatus.result.stats.imported}, skipped:{' '}
                                        {lastStatus.result.stats.skipped}
                                    </span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
            <p className="text-[10px] text-slate-400">
                Auto-refreshes every 15 seconds
            </p>
        </div>
    );
};

const AccuLynxAuditPanel: React.FC = () => {
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const fetchAudit = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('/api/crm/import/acculynx/audit?limit=50');
            const json = await res.json();
            setItems(json.audit || []);
        } catch (err: any) {
            setError(err.message || 'Failed to load audit');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAudit();
        const id = setInterval(fetchAudit, 15000);
        return () => clearInterval(id);
    }, []);

    return (
        <div className="mt-4 p-3 border rounded bg-white shadow-sm space-y-2">
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">AccuLynx Scheduler Audit</h3>
                <button
                    type="button"
                    onClick={fetchAudit}
                    className="px-2 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200"
                >
                    Refresh
                </button>
            </div>
            {loading && <p className="text-xs text-slate-400">Loading…</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
            <div className="space-y-1 max-h-52 overflow-auto">
                {items.length === 0 && (
                    <p className="text-xs text-slate-400">No audit entries yet.</p>
                )}
                {items.map((entry, idx) => (
                    <div
                        key={idx}
                        className="flex items-center justify-between gap-2 text-xs border-b last:border-b-0 pb-1"
                    >
                        <div>
                            <div className="flex gap-2 items-center">
                                <span className="font-medium">{entry.tenant}</span>
                                <span className="text-[10px] px-1 rounded bg-slate-100">
                                    {entry.operation}
                                </span>
                            </div>
                            <p className="text-[10px] text-slate-500">
                                {entry.ts_iso ?? entry.ts}
                            </p>
                        </div>
                        {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                            <pre className="text-[9px] text-slate-400 max-w-[160px] overflow-x-auto">
                                {JSON.stringify(entry.metadata)}
                            </pre>
                        )}
                    </div>
                ))}
            </div>
            <p className="text-[10px] text-slate-400">
                Showing latest scheduler operations (schedule, pause, resume, run-now, delete).
            </p>
        </div>
    );
};

const AgentActionsPanel: React.FC = () => {
    const [output, setOutput] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);
    const [recentRuns, setRecentRuns] = useState<any[]>([]);

    const runAction = async (action: string) => {
        setLoading(true);
        setOutput('');
        try {
            // Emit event for action request
            await fetch('/bus/events', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': 'the-expert-co',
                    'x-ops': '1'
                },
                body: JSON.stringify({
                    source: 'peakpro',
                    type: 'ops.local.run.requested',
                    payload: { action }
                })
            });

            const res = await fetch('/api/local/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': 'the-expert-co',
                },
                body: JSON.stringify({ action }),
            });
            const data = await res.json();
            const lines = [
                `ok: ${data.ok}`,
                data.stdout ? `stdout:\n${data.stdout}` : '',
                data.stderr ? `stderr:\n${data.stderr}` : '',
                data.error ? `error: ${data.error}` : '',
            ]
                .filter(Boolean)
                .join('\n\n');
            setOutput(lines);
            // Refresh recent runs after execution
            fetchRecentRuns();
        } catch (err: any) {
            setOutput(`error: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const fetchRecentRuns = async () => {
        try {
            const res = await fetch('/api/local/runs', {
                headers: { 'x-tenant': 'the-expert-co' }
            });
            if (res.ok) {
                const data = await res.json();
                setRecentRuns(data.runs || []);
            }
        } catch (err) {
            console.error('Failed to fetch recent runs:', err);
        }
    };

    useEffect(() => {
        fetchRecentRuns();
    }, []);

    return (
        <div className="mt-4 p-3 border rounded bg-white shadow-sm space-y-2">
            <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">Agent Actions</h3>
                {loading && <span className="text-xs text-slate-500">Running…</span>}
            </div>
            <div className="flex flex-wrap gap-2">
                <button
                    onClick={() => runAction('status')}
                    className="px-2 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200"
                    disabled={loading}
                >
                    Check local status
                </button>
                <button
                    onClick={() => runAction('list-imports')}
                    className="px-2 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200"
                    disabled={loading}
                >
                    List attachments
                </button>
                <button
                    onClick={() => runAction('rebuild-ui')}
                    className="px-2 py-1 text-xs rounded bg-slate-100 hover:bg-slate-200"
                    disabled={loading}
                >
                    Rebuild UI
                </button>
            </div>
            <pre className="text-[11px] bg-slate-950 text-slate-100 p-2 rounded max-h-40 overflow-auto whitespace-pre-wrap">
                {output || 'No output yet.'}
            </pre>
            {recentRuns.length > 0 && (
                <div className="border-t pt-2">
                    <h4 className="text-xs font-medium text-slate-600 mb-1">Recent Runs</h4>
                    <div className="space-y-1 max-h-32 overflow-auto">
                        {recentRuns.map((run, idx) => (
                            <div key={idx} className="text-[10px] bg-slate-50 p-1 rounded flex justify-between">
                                <span className="font-mono">{run.action}</span>
                                <span className="text-slate-500">
                                    {new Date(run.timestamp * 1000).toLocaleTimeString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

function PeakProCRM() {
    const [bundle, setBundle] = useState<BundleData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentView, setCurrentView] = useState<'pipeline' | 'record' | 'automations'>('pipeline');
    const [selectedRecord, setSelectedRecord] = useState<any>(null);
    const [showNewDealForm, setShowNewDealForm] = useState(false);
    const [newDealTitle, setNewDealTitle] = useState('');
    const [newDealStatus, setNewDealStatus] = useState('Lead');
    const [syncStatus, setSyncStatus] = useState<{ ok: boolean; message: string; ts: number | null } | null>(null);

    // Fallback mock data
    const fallbackDeals = [
        { id: 1, title: 'Commercial Roof Inspection - Tech Corp', customer: 'Tech Corp', value: 45000, stage: 'Qualified', days: 3, createdAt: '2025-01-01', updatedAt: '2025-01-05', description: 'Full commercial roof inspection and assessment', activities: [{ description: 'Initial site visit completed', timestamp: '2025-01-02' }], messages: [{ content: 'Report ready for review', from: 'Inspector Mike', timestamp: '2025-01-03' }], documents: [{ name: 'Inspection Report.pdf' }, { name: 'Site Photos.zip' }] },
        { id: 2, title: 'Emergency Leak Repair - Downtown Building', customer: 'Downtown Properties', value: 8500, stage: 'Proposal', days: 1, createdAt: '2025-01-04', updatedAt: '2025-01-05', description: 'Urgent leak repair in office building', activities: [{ description: 'Emergency response dispatched', timestamp: '2025-01-04' }], messages: [{ content: 'Leak contained, awaiting final quote', from: 'Service Team', timestamp: '2025-01-05' }], documents: [{ name: 'Damage Assessment.pdf' }] },
    ];

    // Use fetched data or fall back to mock data
    const rawRecords = bundle?.records || fallbackDeals;
    const deals = rawRecords.map(record => ({
        id: record.id,
        title: record.title,
        customer: record.owner || 'Unknown', // Map owner to customer
        value: 0, // Default value, could be enhanced later
        stage: record.status || 'Lead', // Map status to stage
        days: 1, // Default, could calculate from created_at
        createdAt: record.created_at,
        updatedAt: record.created_at,
        description: record.next_action || '',
        activities: [], // Could map from activities
        messages: [],
        documents: []
    }));

    const peakproRules = [
        { id: '1', name: 'Emergency leak alerts', trigger: { event: 'Leak Detected', conditions: [{ field: 'severity', operator: '==', value: 'critical' }] }, actions: [{ type: 'Dispatch', description: 'Send emergency response team' }, { type: 'Notification', description: 'Alert property manager' }], enabled: true },
        { id: '2', name: 'Follow-up on completed inspections', trigger: { event: 'Inspection Completed', conditions: [] }, actions: [{ type: 'Email', description: 'Send inspection report and quote' }], enabled: true },
    ];

    const fetchBundle = async () => {
        try {
            // Try to fetch CRM data first
            let crmData = null;
            try {
                const crmResponse = await fetch('/api/crm/peakpro/bundle', {
                    headers: { 'x-tenant': 'the-expert-co' }
                });
                if (crmResponse.ok) {
                    crmData = await crmResponse.json();
                }
            } catch (crmErr) {
                console.log('CRM bundle not available, using ops bundle only');
            }

            // Fetch ops bundle
            const opsResponse = await fetch('/ui/bundle');
            if (!opsResponse.ok) throw new Error('Failed to fetch ops bundle');
            const opsData = await opsResponse.json();

            // Merge data: CRM data takes precedence for CRM fields
            const mergedData = { ...opsData, ...crmData };
            setBundle(mergedData);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            // Use mock data for demonstration
            setBundle({
                status: { services: [{ name: 'peakpro-crm', up: true }, { name: 'roofwonder', up: true }] },
                federation: { status: 'healthy', peers_up: 3, peers_total: 3 },
                opt: {},
                learn: { explanation: 'PeakPro optimization active - focusing on emergency response times' },
                policies: { active_policies: { 'response.sla.emergency': { value: 2, source: 'federated', version: 3 } }, pending_proposals: [] },
                alerts: []
            });
        } finally {
            setLoading(false);
        }
    };

    const fetchSyncStatus = async () => {
        try {
            const resp = await fetch('/api/crm/import/status', {
                headers: { 'x-tenant': 'the-expert-co' }
            });
            const data = await resp.json();
            setSyncStatus(data);
        } catch (error) {
            console.error('Failed to fetch sync status:', error);
        }
    };

    useEffect(() => {
        fetchBundle();
        fetchSyncStatus();
        const id = setInterval(fetchSyncStatus, 15000);
        return () => clearInterval(id);
    }, []);

    const handleDealClick = (deal: any) => {
        setSelectedRecord(deal);
        setCurrentView('record');
    };

    const handleNewDeal = async () => {
        if (!newDealTitle.trim()) {
            alert('Please enter a job title');
            return;
        }

        try {
            const response = await fetch('/api/crm/peakpro/record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': 'the-expert-co'
                },
                body: JSON.stringify({
                    title: newDealTitle.trim(),
                    status: newDealStatus
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create job');
            }

            const newRecord = await response.json();

            // Refresh the bundle to get updated data
            await fetchBundle();

            // Reset form
            setNewDealTitle('');
            setNewDealStatus('Lead');
            setShowNewDealForm(false);

            // Switch to the new record view
            setSelectedRecord(newRecord);
            setCurrentView('record');

        } catch (error) {
            console.error('Error creating job:', error);
            alert('Failed to create job. Please try again.');
        }
    };

    const handleUpdateRecord = async (recordId: string, updates: any) => {
        try {
            const response = await fetch(`/api/crm/peakpro/record/${recordId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': 'the-expert-co'
                },
                body: JSON.stringify(updates)
            });

            if (!response.ok) {
                throw new Error('Failed to update job');
            }

            const updatedRecord = await response.json();

            // Refresh the bundle to get updated data
            await fetchBundle();

            // Update the selected record
            setSelectedRecord(updatedRecord);

        } catch (error) {
            console.error('Error updating job:', error);
            alert('Failed to update job. Please try again.');
        }
    };

    const handleRuleUpdate = (rule: any) => {
        console.log('Update PeakPro rule:', rule);
    };

    const handleRuleDelete = (id: string) => {
        console.log('Delete PeakPro rule:', id);
    };

    const handleResync = async () => {
        try {
            const resp = await fetch('/api/crm/import/acculynx/pull', {
                method: 'POST',
                headers: {
                    'x-tenant': 'the-expert-co',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({}),
            });
            if (resp.ok) {
                // re-fetch CRM data
                await fetchBundle();
            } else {
                console.error('Resync failed', await resp.text());
                alert('Failed to resync from AccuLynx');
            }
        } catch (error) {
            console.error('Resync error:', error);
            alert('Error resyncing from AccuLynx');
        }
    };

    const setSchedule = async (intervalSec: number) => {
        try {
            const resp = await fetch('/api/crm/import/acculynx/schedule', {
                method: 'POST',
                headers: {
                    'x-tenant': 'the-expert-co',
                    'Content-Type': 'application/json',
                    'x-ops': '1',  // Phase XII: Mark as operator action
                },
                body: JSON.stringify({ interval_sec: intervalSec }),
            });
            if (resp.ok) {
                alert(`Scheduled sync every ${intervalSec / 60} minutes`);
            } else {
                alert('Failed to set schedule');
            }
        } catch (error) {
            console.error('Schedule error:', error);
            alert('Error setting schedule');
        }
    };

    if (loading) return <div className="flex items-center justify-center h-screen">Loading PeakPro CRM...</div>;
    if (error && !bundle) return <div className="flex items-center justify-center h-screen text-red-600">Error: {error}</div>;

    return (
        <CrmShell title="PeakPro CRM - Roofing Services" bundle={bundle}>
            <div className="h-full">
                {/* View Tabs */}
                <div className="border-b border-gray-200 bg-white">
                    <div className="px-6">
                        <nav className="flex space-x-8">
                            <button
                                onClick={() => setCurrentView('pipeline')}
                                className={`py-4 px-1 border-b-2 font-medium text-sm ${currentView === 'pipeline'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                Pipeline
                            </button>
                            <button
                                onClick={() => setCurrentView('record')}
                                className={`py-4 px-1 border-b-2 font-medium text-sm ${currentView === 'record'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                Record
                            </button>
                            <button
                                onClick={() => setCurrentView('automations')}
                                className={`py-4 px-1 border-b-2 font-medium text-sm ${currentView === 'automations'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                Automations
                            </button>
                        </nav>
                    </div>
                </div>

                {/* Action Bar */}
                <div className="bg-white border-b border-gray-200 px-6 py-3">
                    <div className="flex justify-between items-center">
                        <div className="flex items-center gap-4">
                            <div className="text-sm text-gray-600">
                                {bundle?.last_synced_at && (
                                    <span>Last synced: {new Date(bundle.last_synced_at * 1000).toLocaleString()}</span>
                                )}
                            </div>
                            {syncStatus && (
                                <span className={`text-xs px-2 py-1 rounded ${syncStatus.ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                                    {syncStatus.ok ? 'Sync OK' : 'Sync Error'} • {syncStatus.message}
                                </span>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setSchedule(300)}
                                className="px-3 py-1 rounded bg-green-100 hover:bg-green-200 text-green-700 text-sm border border-green-300"
                            >
                                Auto-sync 5m
                            </button>
                            <button
                                onClick={() => setSchedule(900)}
                                className="px-3 py-1 rounded bg-green-100 hover:bg-green-200 text-green-700 text-sm border border-green-300"
                            >
                                Auto-sync 15m
                            </button>
                            <button
                                onClick={handleResync}
                                className="px-3 py-1 rounded bg-blue-100 hover:bg-blue-200 text-blue-700 text-sm border border-blue-300"
                            >
                                Re-sync from AccuLynx
                            </button>
                        </div>
                    </div>
                </div>
                <div className="flex-1">
                    <AgentActionsPanel />
                    <AccuLynxSchedulePanel />
                    <AccuLynxAuditPanel />
                    {showNewDealForm && (
                        <div className="p-6 bg-white border-b border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Create New Job</h3>
                            <div className="flex gap-4 mb-4">
                                <input
                                    type="text"
                                    placeholder="Job title"
                                    value={newDealTitle}
                                    onChange={(e) => setNewDealTitle(e.target.value)}
                                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <select
                                    value={newDealStatus}
                                    onChange={(e) => setNewDealStatus(e.target.value)}
                                    className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    aria-label="Job status"
                                >
                                    <option value="Lead">Lead</option>
                                    <option value="Qualified">Qualified</option>
                                    <option value="Proposal">Proposal</option>
                                    <option value="Active">Active</option>
                                </select>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={handleNewDeal}
                                    className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                                >
                                    Create Job
                                </button>
                                <button
                                    onClick={() => setShowNewDealForm(false)}
                                    className="bg-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-400 transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    )}
                    {currentView === 'pipeline' && (
                        <PipelineView
                            deals={deals}
                            onDealClick={handleDealClick}
                            onNewDeal={() => setShowNewDealForm(true)}
                        />
                    )}
                    {currentView === 'record' && (
                        <RecordView
                            record={selectedRecord}
                            onUpdate={handleUpdateRecord}
                            files={bundle?.files?.filter((f: any) => f.job_id === selectedRecord?.id) || []}
                        />
                    )}
                    {currentView === 'automations' && (
                        <AutomationsView
                            rules={peakproRules}
                            onRuleUpdate={handleRuleUpdate}
                            onRuleDelete={handleRuleDelete}
                        />
                    )}
                </div>
            </div>
        </CrmShell>
    )
}

export default PeakProCRM
