import { useState, useEffect } from 'react'
import { CrmShell, PipelineView, RecordView, AutomationsView } from '../crm-lib'

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
}

function PolicyPalCRM() {
    const [bundle, setBundle] = useState<BundleData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [currentView, setCurrentView] = useState<'pipeline' | 'record' | 'automations'>('pipeline');
    const [selectedRecord, setSelectedRecord] = useState<any>(null);
    const [showNewDealForm, setShowNewDealForm] = useState(false);
    const [newDealTitle, setNewDealTitle] = useState('');
    const [newDealStatus, setNewDealStatus] = useState('Lead');

    // Fallback mock data
    const fallbackDeals = [
        { id: 1, title: 'Commercial Property Insurance - ABC Corp', customer: 'ABC Corporation', value: 125000, stage: 'Negotiation', days: 15, createdAt: '2024-12-15', updatedAt: '2025-01-05', description: 'Comprehensive commercial property insurance coverage', activities: [{ description: 'Risk assessment completed', timestamp: '2024-12-20' }, { description: 'Quote presented to client', timestamp: '2025-01-02' }], messages: [{ content: 'Please review the attached quote', from: 'Underwriter Sarah', timestamp: '2025-01-02' }], documents: [{ name: 'Risk Assessment.pdf' }, { name: 'Insurance Quote.pdf' }] },
        { id: 2, title: 'Homeowners Policy - Smith Family', customer: 'John & Jane Smith', value: 1800, stage: 'Closed Won', days: 8, createdAt: '2024-12-28', updatedAt: '2025-01-05', description: 'Standard homeowners insurance with flood coverage', activities: [{ description: 'Application submitted', timestamp: '2025-01-01' }, { description: 'Policy issued', timestamp: '2025-01-05' }], messages: [{ content: 'Policy documents attached', from: 'Policy Admin', timestamp: '2025-01-05' }], documents: [{ name: 'Policy Documents.pdf' }] },
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

    const policypalRules = [
        { id: '1', name: 'High-value policy alerts', trigger: { event: 'Quote Generated', conditions: [{ field: 'premium', operator: '>', value: 50000 }] }, actions: [{ type: 'Notification', description: 'Alert senior underwriter' }, { type: 'Email', description: 'Send compliance checklist' }], enabled: true },
        { id: '2', name: 'Policy renewal reminders', trigger: { event: 'Policy Expires Soon', conditions: [{ field: 'days_until_expiry', operator: '<', value: 30 }] }, actions: [{ type: 'Email', description: 'Send renewal quote automatically' }], enabled: true },
    ];

    const fetchBundle = async () => {
        try {
            // Try to fetch CRM data first
            let crmData = null;
            try {
                const crmResponse = await fetch('/api/crm/policypal/bundle', {
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
                status: { services: [{ name: 'policypal-ai', up: true }, { name: 'peakpro-crm', up: true }] },
                federation: { status: 'healthy', peers_up: 3, peers_total: 3 },
                opt: {},
                learn: { explanation: 'PolicyPal learning active - optimizing quote acceptance rates' },
                policies: { active_policies: { 'quotes.auto_approve_under': { value: 2500, source: 'federated', version: 2 } }, pending_proposals: [] },
                alerts: []
            });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchBundle();
        const interval = setInterval(fetchBundle, 30000);
        return () => clearInterval(interval);
    }, []);

    const handleDealClick = (deal: any) => {
        setSelectedRecord(deal);
        setCurrentView('record');
    };

    const handleNewDeal = async () => {
        if (!newDealTitle.trim()) {
            alert('Please enter a policy title');
            return;
        }

        try {
            const response = await fetch('/api/crm/policypal/record', {
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
                throw new Error('Failed to create policy');
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
            console.error('Error creating policy:', error);
            alert('Failed to create policy. Please try again.');
        }
    };

    const handleUpdateRecord = async (recordId: string, updates: any) => {
        try {
            const response = await fetch(`/api/crm/policypal/record/${recordId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'x-tenant': 'the-expert-co'
                },
                body: JSON.stringify(updates)
            });

            if (!response.ok) {
                throw new Error('Failed to update policy');
            }

            const updatedRecord = await response.json();

            // Refresh the bundle to get updated data
            await fetchBundle();

            // Update the selected record
            setSelectedRecord(updatedRecord);

        } catch (error) {
            console.error('Error updating policy:', error);
            alert('Failed to update policy. Please try again.');
        }
    };

    const handleRuleUpdate = (rule: any) => {
        console.log('Update PolicyPal rule:', rule);
    };

    const handleRuleDelete = (id: string) => {
        console.log('Delete PolicyPal rule:', id);
    };

    if (loading) return <div className="flex items-center justify-center h-screen">Loading PolicyPal CRM...</div>;
    if (error && !bundle) return <div className="flex items-center justify-center h-screen text-red-600">Error: {error}</div>;

    return (
        <CrmShell title="PolicyPal CRM - Insurance Services" bundle={bundle}>
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

                {/* View Content */}
                <div className="flex-1">
                    {showNewDealForm && (
                        <div className="p-6 bg-white border-b border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Create New Policy</h3>
                            <div className="flex gap-4 mb-4">
                                <input
                                    type="text"
                                    placeholder="Policy title"
                                    value={newDealTitle}
                                    onChange={(e) => setNewDealTitle(e.target.value)}
                                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                                <select
                                    value={newDealStatus}
                                    onChange={(e) => setNewDealStatus(e.target.value)}
                                    className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    aria-label="Policy status"
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
                                    Create Policy
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
                        <RecordView record={selectedRecord} onUpdate={handleUpdateRecord} files={bundle?.files?.filter((f: any) => f.job_id === selectedRecord?.id) || []} />
                    )}
                    {currentView === 'automations' && (
                        <AutomationsView
                            rules={policypalRules}
                            onRuleUpdate={handleRuleUpdate}
                            onRuleDelete={handleRuleDelete}
                        />
                    )}
                </div>
            </div>
        </CrmShell>
    )
}

export default PolicyPalCRM