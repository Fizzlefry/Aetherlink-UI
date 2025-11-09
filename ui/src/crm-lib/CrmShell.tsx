import { useState } from 'react';

interface CrmShellProps {
    children: React.ReactNode;
    title: string;
    bundle: any;
}

export function CrmShell({ children, title, bundle }: CrmShellProps) {
    const [sidebarOpen, setSidebarOpen] = useState(true);

    return (
        <div className="h-screen flex flex-col bg-gray-50">
            {/* Top App Bar */}
            <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className="p-2 rounded-lg hover:bg-gray-100"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                    </button>
                    <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
                </div>
                <div className="flex items-center space-x-4">
                    {/* AetherLink Status */}
                    <div className="flex items-center space-x-2">
                        <div className={`w-2 h-2 rounded-full ${bundle?.federation?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></div>
                        <span className="text-sm text-gray-600">AetherLink</span>
                    </div>
                </div>
            </header>

            <div className="flex flex-1 overflow-hidden">
                {/* Left Nav */}
                {sidebarOpen && (
                    <nav className="w-64 bg-white border-r border-gray-200 p-4">
                        <div className="space-y-2">
                            <button className="w-full text-left px-3 py-2 rounded-lg bg-blue-50 text-blue-700 font-medium">
                                Overview
                            </button>
                            <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 text-gray-700">
                                Communications
                            </button>
                            <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 text-gray-700">
                                Documents
                            </button>
                            <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 text-gray-700">
                                Automations
                            </button>
                        </div>
                    </nav>
                )}

                {/* Main Content */}
                <main className="flex-1 overflow-auto">
                    {children}
                </main>

                {/* Right Rail */}
                <aside className="w-80 bg-white border-l border-gray-200 p-4">
                    <div className="space-y-4">
                        {/* Service Status */}
                        <div>
                            <h3 className="font-medium text-gray-900 mb-2">Service Status</h3>
                            <div className="space-y-1">
                                {bundle?.status?.services?.map((service: any) => (
                                    <div key={service.name} className="flex items-center justify-between">
                                        <span className="text-sm text-gray-600">{service.name}</span>
                                        <div className={`w-2 h-2 rounded-full ${service.up ? 'bg-green-500' : 'bg-red-500'}`}></div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Active Alerts */}
                        <div>
                            <h3 className="font-medium text-gray-900 mb-2">Active Alerts</h3>
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                                {bundle?.alerts?.slice(0, 3).map((alert: any, i: number) => (
                                    <div key={i} className="text-xs p-2 bg-red-50 rounded border-l-2 border-red-500">
                                        {alert.summary}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Federation Health */}
                        <div>
                            <h3 className="font-medium text-gray-900 mb-2">Federation</h3>
                            <div className="text-sm text-gray-600">
                                <div>Status: {bundle?.federation?.status}</div>
                                <div>Peers: {bundle?.federation?.peers_up}/{bundle?.federation?.peers_total}</div>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
}