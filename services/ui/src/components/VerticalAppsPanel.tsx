/**
 * VerticalAppsPanel - Unified view of all vertical apps via Command Center aggregator
 *
 * Fetches from http://localhost:8010/verticals/stats and displays:
 * - PeakPro CRM (contacts, deals)
 * - RoofWonder (jobs, photos)
 * - PolicyPal AI (policies)
 * - Media Service (uploads)
 */

import { useEffect, useState } from 'react';

interface ServiceSummary {
  contacts?: number;
  deals?: number;
  jobs?: number;
  photos?: number;
  policies?: number;
  uploads?: number;
  total_files?: number;
}

interface AttributionData {
  last_created_by_key?: string;
  last_created_by_key_label?: string;
  last_created_by_key_metadata?: {
    label: string;
    role: string;
    owner: string;
    status: string;
  };
  top_creator_keys?: Array<{
    key: string;
    count: number;
    label?: string;
    metadata?: {
      label: string;
      role: string;
      owner: string;
      status: string;
    };
  }>;
}

interface ServiceData {
  summary: ServiceSummary;
  attribution?: AttributionData;
  error?: string;
}

interface VerticalStatsResponse {
  timestamp: string;
  services: Record<string, ServiceData>;
  summary?: {
    total_contacts?: number;
    total_deals?: number;
    total_jobs?: number;
    total_properties?: number;
    total_policies?: number;
    total_uploads?: number;
    stale_services?: string[];
    attribution?: AttributionData;
  };
}

export function VerticalAppsPanel() {
  const [stats, setStats] = useState<VerticalStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('http://localhost:8010/verticals/stats', {
          headers: { 'X-User-Roles': 'operator' }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setStats(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-4">
            <div className="h-32 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-semibold mb-2">Error Loading Apps</h3>
          <p className="text-red-600">{error}</p>
          <p className="text-sm text-red-500 mt-2">
            Make sure the Command Center is running on port 8010
          </p>
        </div>
      </div>
    );
  }

  const { services } = stats || { services: {} as Record<string, ServiceData> };
  const platform = stats?.summary;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Vertical Apps Dashboard</h2>
        <div className="text-sm text-gray-500">
          Last updated: {stats?.timestamp ? new Date(stats.timestamp).toLocaleTimeString() : 'N/A'}
        </div>
      </div>

      {/* Platform Totals */}
      {platform && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="rounded-md border bg-white dark:bg-slate-900 dark:border-slate-700 p-3">
            <p className="text-xs text-slate-500 dark:text-slate-400">Total contacts</p>
            <p className="text-lg font-semibold">{platform.total_contacts ?? 0}</p>
          </div>
          <div className="rounded-md border bg-white dark:bg-slate-900 dark:border-slate-700 p-3">
            <p className="text-xs text-slate-500 dark:text-slate-400">Total jobs</p>
            <p className="text-lg font-semibold">{platform.total_jobs ?? 0}</p>
          </div>
          <div className="rounded-md border bg-white dark:bg-slate-900 dark:border-slate-700 p-3">
            <p className="text-xs text-slate-500 dark:text-slate-400">Total uploads</p>
            <p className="text-lg font-semibold">{platform.total_uploads ?? 0}</p>
          </div>
        </div>
      )}

      {/* Platform Attribution */}
      {platform?.attribution && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-blue-800 mb-2">Platform Activity</h3>
          <div className="space-y-2">
            {platform.attribution.last_created_by_key && (
              <p className="text-sm text-blue-700">
                <span className="font-medium">Last write by:</span> {platform.attribution.last_created_by_key_label || platform.attribution.last_created_by_key}
                {platform.attribution.last_created_by_key_metadata && (
                  <span className="text-xs text-blue-500 ml-2">
                    ({platform.attribution.last_created_by_key_metadata.role})
                  </span>
                )}
              </p>
            )}
            {platform.attribution.top_creator_keys && platform.attribution.top_creator_keys.length > 0 && (
              <div className="text-sm text-blue-700">
                <span className="font-medium">Top contributors:</span>
                <div className="mt-1 space-y-1">
                  {platform.attribution.top_creator_keys.slice(0, 3).map((item) => (
                    <div key={item.key} className="flex justify-between">
                      <span>{item.label || item.key}</span>
                      <span className="font-mono text-xs bg-blue-100 px-2 py-1 rounded">
                        {item.count} writes
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stale Services Warning */}
      {platform?.stale_services?.length ? (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <p className="text-sm text-amber-700">
            ⚠️ Stale data from: {platform.stale_services.join(", ")}
          </p>
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* PeakPro CRM */}
        <PeakProCard data={services['peakpro-crm']} />

        {/* RoofWonder */}
        <RoofWonderCard data={services['roofwonder']} />

        {/* PolicyPal AI */}
        <PolicyPalCard data={services['policypal-ai']} />

        {/* Media Service */}
        <MediaServiceCard data={services['media-service']} />
      </div>
    </div>
  );
}

function PeakProCard({ data }: { data: ServiceData | undefined }) {
  if (!data || data.error) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">PeakPro CRM</h3>
        <p className="text-sm text-gray-500">
          {data?.error ? `Error: ${data.error}` : 'Offline or not configured'}
        </p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-blue-700">PeakPro CRM</h3>
        <span className="text-xs text-gray-500">Port 8021</span>
      </div>

      <div className="space-y-3">
        {/* Contacts */}
        <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
          <span className="text-sm font-medium text-gray-700">Contacts</span>
          <span className="text-lg font-bold text-blue-600">{summary.contacts || 0}</span>
        </div>

        {/* Deals */}
        <div className="flex justify-between items-center p-3 bg-green-50 rounded">
          <span className="text-sm font-medium text-gray-700">Deals</span>
          <span className="text-lg font-bold text-green-600">{summary.deals || 0}</span>
        </div>
      </div>

      {/* Attribution */}
      {data.attribution && (
        <div className="mt-4 p-3 bg-gray-50 rounded border">
          <p className="text-xs text-gray-600 mb-1">Last activity</p>
          {data.attribution.last_created_by_key && (
            <p className="text-sm font-mono text-gray-800">
              {data.attribution.last_created_by_key_label || data.attribution.last_created_by_key}
            </p>
          )}
        </div>
      )}

      <div className="mt-4 pt-4 border-t border-gray-200">
        <a
          href="http://localhost:8021/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
        >
          View API Docs →
        </a>
      </div>
    </div>
  );
}

function RoofWonderCard({ data }: { data: ServiceData | undefined }) {
  if (!data || data.error) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">RoofWonder</h3>
        <p className="text-sm text-gray-500">
          {data?.error ? `Error: ${data.error}` : 'Offline or not configured'}
        </p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-orange-700">RoofWonder</h3>
        <span className="text-xs text-gray-500">Port 8022</span>
      </div>

      <div className="space-y-3">
        {/* Jobs */}
        <div className="flex justify-between items-center p-3 bg-orange-50 rounded">
          <span className="text-sm font-medium text-gray-700">Jobs</span>
          <span className="text-lg font-bold text-orange-600">{summary.jobs || 0}</span>
        </div>

        {/* Photos */}
        <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
          <span className="text-sm font-medium text-gray-700">Photos</span>
          <span className="text-lg font-bold text-blue-600">{summary.photos || 0}</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <a
          href="http://localhost:8022/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-orange-600 hover:text-orange-800 hover:underline"
        >
          View API Docs →
        </a>
      </div>
    </div>
  );
}

function PolicyPalCard({ data }: { data: ServiceData | undefined }) {
  if (!data || data.error) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">PolicyPal AI</h3>
        <p className="text-sm text-gray-500">
          {data?.error ? `Error: ${data.error}` : 'Offline or not configured'}
        </p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-purple-700">PolicyPal AI</h3>
        <span className="text-xs text-gray-500">Port 8023</span>
      </div>

      <div className="space-y-3">
        {/* Policies */}
        <div className="flex justify-between items-center p-3 bg-purple-50 rounded">
          <span className="text-sm font-medium text-gray-700">Policies</span>
          <span className="text-lg font-bold text-purple-600">{summary.policies || 0}</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <a
          href="http://localhost:8023/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-purple-600 hover:text-purple-800 hover:underline"
        >
          View API Docs →
        </a>
      </div>
    </div>
  );
}

function MediaServiceCard({ data }: { data: ServiceData | undefined }) {
  if (!data || data.error) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">Media Service</h3>
        <p className="text-sm text-gray-500">
          {data?.error ? `Error: ${data.error}` : 'Offline or not configured'}
        </p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-green-700">Media Service</h3>
        <span className="text-xs text-gray-500">Port 9109</span>
      </div>

      <div className="space-y-3">
        {/* Files */}
        <div className="flex justify-between items-center p-3 bg-green-50 rounded">
          <span className="text-sm font-medium text-gray-700">Files</span>
          <span className="text-lg font-bold text-green-600">{summary.total_files || 0}</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <a
          href="http://localhost:9109/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-green-600 hover:text-green-800 hover:underline"
        >
          View API Docs →
        </a>
      </div>
    </div>
  );
}
