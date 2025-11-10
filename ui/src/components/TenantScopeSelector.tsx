import { useState, useEffect } from "react";

type Tenant = {
    id: string;
    name: string;
    status: string;
    profile: string;
    created_at: string;
    demo: boolean;
    env: string;
    ai_auto_enabled: boolean;
    auto_budget_per_hour: number;
};

type TenantScopeSelectorProps = {
    selectedTenant: string | null;
    onTenantChange: (tenant: string | null) => void;
};

export function TenantScopeSelector({ selectedTenant, onTenantChange }: TenantScopeSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchTenants = async () => {
            try {
                const response = await fetch('/tenants', {
                    headers: {
                        'x-api-key': localStorage.getItem('apiKey') || '',
                        'x-admin-key': localStorage.getItem('adminKey') || '',
                    },
                });

                if (!response.ok) {
                    throw new Error('Failed to fetch tenants');
                }

                const data = await response.json();
                setTenants(data.tenants || []);
            } catch (err) {
                console.error('Error fetching tenants:', err);
                // Fallback to hardcoded tenants if API fails
                setTenants([
                    { id: "the-expert-co", name: "ExpertCo", status: "active", profile: "enterprise", created_at: "", demo: false, env: "prod", ai_auto_enabled: true, auto_budget_per_hour: 50 },
                    { id: "roofwonder", name: "RoofWonder", status: "active", profile: "general", created_at: "", demo: false, env: "prod", ai_auto_enabled: true, auto_budget_per_hour: 10 },
                    { id: "policypal", name: "PolicyPal", status: "archived", profile: "general", created_at: "", demo: false, env: "prod", ai_auto_enabled: false, auto_budget_per_hour: 0 },
                    { id: "peakpro", name: "PeakPro", status: "archived", profile: "general", created_at: "", demo: false, env: "prod", ai_auto_enabled: false, auto_budget_per_hour: 0 },
                ]);
            } finally {
                setLoading(false);
            }
        };

        fetchTenants();
    }, []);

    const activeTenants = tenants.filter(t => t.status === 'active');
    const inactiveTenants = tenants.filter(t => t.status !== 'active');
    const currentTenant = selectedTenant ? tenants.find(t => t.id.toLowerCase() === selectedTenant.toLowerCase()) : null;

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-md text-sm hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                disabled={loading}
            >
                <span className="text-slate-700 dark:text-slate-300">
                    {loading ? "Loading..." : currentTenant ? currentTenant.name : "All Tenants"}
                </span>
                <span className="text-slate-500 dark:text-slate-400">
                    {isOpen ? "▲" : "▼"}
                </span>
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-48 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-md shadow-lg z-10">
                    <div className="py-1">
                        <button
                            onClick={() => {
                                onTenantChange(null);
                                setIsOpen(false);
                            }}
                            className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 ${selectedTenant === null ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'text-slate-700 dark:text-slate-300'
                                }`}
                        >
                            All Tenants
                        </button>
                        {activeTenants.map((tenant) => (
                            <button
                                key={tenant.id}
                                onClick={() => {
                                    onTenantChange(tenant.id);
                                    setIsOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 ${selectedTenant === tenant.id ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'text-slate-700 dark:text-slate-300'
                                    }`}
                            >
                                <div className="flex justify-between items-center">
                                    <span>{tenant.name}</span>
                                    <div className="flex items-center gap-2 text-xs">
                                        {tenant.ai_auto_enabled ? (
                                            <span className="text-green-600 dark:text-green-400">AI ✓</span>
                                        ) : (
                                            <span className="text-red-600 dark:text-red-400">AI ✗</span>
                                        )}
                                        <span className="text-slate-500 dark:text-slate-400">
                                            {tenant.auto_budget_per_hour}/hr
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                    {inactiveTenants.length > 0 && (
                        <>
                            <div className="border-t border-slate-200 dark:border-slate-600"></div>
                            <div className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                                Archived:
                                {inactiveTenants.map(t => t.name).join(", ")}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
