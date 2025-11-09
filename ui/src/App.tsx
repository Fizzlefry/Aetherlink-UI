import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { DashboardHome } from './DashboardHome';
import PeakProCRM from './verticals/PeakProCRM';
import PolicyPalCRM from './verticals/PolicyPalCRM';

interface BundleData {
  status: any;
  federation: any;
  opt: any;
  learn: any;
  policies: any;
  alerts: any[];
}

function App() {
  const [bundle, setBundle] = useState<BundleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBundle = async () => {
    try {
      const response = await fetch('http://localhost:8011/ui/bundle');
      if (!response.ok) throw new Error('Failed to fetch bundle');
      const data = await response.json();
      setBundle(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      // Use mock data for demonstration
      setBundle({
        status: {
          services: [
            { name: 'peakpro-crm', up: true },
            { name: 'policypal-crm', up: true },
            { name: 'roofwonder', up: false },
            { name: 'clientellme', up: false },
            { name: 'apexflow', up: false }
          ]
        },
        federation: { status: 'healthy', peers_up: 3, peers_total: 3 },
        opt: {},
        learn: { explanation: 'AetherLink learning active across all verticals' },
        policies: {
          active_policies: {
            'response.sla.emergency': { value: 2, source: 'federated', version: 3 },
            'alerts.autoheal.enabled': { value: true, source: 'federated', version: 2 }
          },
          pending_proposals: []
        },
        alerts: [
          { fingerprint: 'alert-1', description: 'High memory usage detected', severity: 'warning' }
        ]
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBundle();
    const interval = setInterval(fetchBundle, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading AetherLink CRM...</p>
        </div>
      </div>
    );
  }

  if (error && !bundle) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center">
          <div className="text-red-600 mb-4">⚠️ Error loading dashboard</div>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={fetchBundle}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<DashboardHome bundle={bundle} />} />
        <Route path="/peakpro" element={<PeakProCRM />} />
        <Route path="/policypal" element={<PolicyPalCRM />} />
        {/* Placeholder routes for future verticals */}
        <Route path="/roofwonder" element={
          <div className="flex items-center justify-center min-h-screen bg-slate-50">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">RoofWonder CRM</h1>
              <p className="text-gray-600">Coming Soon...</p>
            </div>
          </div>
        } />
        <Route path="/clientellme" element={
          <div className="flex items-center justify-center min-h-screen bg-slate-50">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">Clientellme CRM</h1>
              <p className="text-gray-600">Coming Soon...</p>
            </div>
          </div>
        } />
        <Route path="/apexflow" element={
          <div className="flex items-center justify-center min-h-screen bg-slate-50">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">ApexFlow CRM</h1>
              <p className="text-gray-600">Coming Soon...</p>
            </div>
          </div>
        } />
      </Routes>
    </Router>
  );
}

export default App
