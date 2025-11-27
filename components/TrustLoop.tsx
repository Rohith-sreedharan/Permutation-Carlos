import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

// SVG Icons (replacing lucide-react)
const CheckCircle = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const XCircle = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const TrendingUp = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
  </svg>
);

const Award = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
  </svg>
);

const Shield = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
  </svg>
);

interface TrustMetrics {
  accuracy: number;
  win_rate: number;
  total_verified: number;
  correct: number;
  incorrect: number;
  window_days: number;
}

interface LedgerEntry {
  creator_id: string;
  creator_name: string;
  forecast: string;
  confidence: number;
  result: string;
  event: string;
  verified_at: string;
  sport: string;
}

const TrustLoop: React.FC = () => {
  const [selectedWindow, setSelectedWindow] = useState<7 | 30 | 90>(7);
  const [metrics, setMetrics] = useState<Record<number, TrustMetrics>>({
    7: { accuracy: 0, win_rate: 0, total_verified: 0, correct: 0, incorrect: 0, window_days: 7 },
    30: { accuracy: 0, win_rate: 0, total_verified: 0, correct: 0, incorrect: 0, window_days: 30 },
    90: { accuracy: 0, win_rate: 0, total_verified: 0, correct: 0, incorrect: 0, window_days: 90 },
  });
  const [publicLedger, setPublicLedger] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTrustData();
    // Refresh every 5 minutes
    const interval = setInterval(loadTrustData, 300000);
    return () => clearInterval(interval);
  }, []);

  const loadTrustData = async () => {
    try {
      setLoading(true);

      // Fetch metrics for all windows
      const windows = [7, 30, 90];
      const metricsData: Record<number, TrustMetrics> = {};

      for (const days of windows) {
        const response = await fetch(`http://localhost:8000/api/verification/metrics?days=${days}`);
        if (response.ok) {
          metricsData[days] = await response.json();
        }
      }

      setMetrics(metricsData);

      // Fetch public ledger
      const ledgerResponse = await fetch('http://localhost:8000/api/verification/ledger');
      if (ledgerResponse.ok) {
        const ledgerData = await ledgerResponse.json();
        setPublicLedger(ledgerData);
      }
    } catch (error) {
      console.error('Failed to load trust data:', error);
    } finally {
      setLoading(false);
    }
  };

  const currentMetrics = metrics[selectedWindow];

  const chartData = [
    { name: '7 Days', accuracy: metrics[7].accuracy * 100, verified: metrics[7].total_verified },
    { name: '30 Days', accuracy: metrics[30].accuracy * 100, verified: metrics[30].total_verified },
    { name: '90 Days', accuracy: metrics[90].accuracy * 100, verified: metrics[90].total_verified },
  ];

  const getAccuracyColor = (accuracy: number) => {
    if (accuracy >= 0.60) return 'text-green-400';
    if (accuracy >= 0.55) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getAccuracyBgColor = (accuracy: number) => {
    if (accuracy >= 0.60) return 'bg-green-500/20';
    if (accuracy >= 0.55) return 'bg-yellow-500/20';
    return 'bg-red-500/20';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-lg p-6 border border-purple-500/30">
        <div className="flex items-center gap-3 mb-2">
          <TrendingUp className="w-8 h-8 text-purple-400" />
          <h2 className="text-2xl font-bold text-white">Trust & Performance Loop</h2>
        </div>
        <p className="text-gray-300">
          Radical transparency. Every forecast is verified against real outcomes.
          <span className="block text-sm text-gray-400 mt-1">
            All accuracy metrics are calculated from publicly verifiable game results.
          </span>
        </p>
      </div>

      {/* Window Selector */}
      <div className="flex gap-2">
        {[7, 30, 90].map((days) => (
          <button
            key={days}
            onClick={() => setSelectedWindow(days as 7 | 30 | 90)}
            className={`px-4 py-2 rounded-lg font-semibold transition-all ${
              selectedWindow === days
                ? 'bg-purple-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {days} Days
          </button>
        ))}
      </div>

      {/* Rolling Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className={`rounded-lg p-4 ${getAccuracyBgColor(currentMetrics.accuracy)} border border-purple-500/30`}>
          <div className="text-gray-400 text-sm mb-1">Model Accuracy</div>
          <div className={`text-3xl font-bold ${getAccuracyColor(currentMetrics.accuracy)}`}>
            {(currentMetrics.accuracy * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">{selectedWindow}-day window</div>
          <div className="text-xs text-gray-400 mt-2 leading-relaxed">
            High-confidence forecasts resolved in the last {selectedWindow} days
          </div>
        </div>

        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">Total Verified</div>
          <div className="text-3xl font-bold text-white">{currentMetrics.total_verified}</div>
          <div className="text-xs text-gray-500 mt-1">Forecasts resolved</div>
        </div>

        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/30">
          <div className="text-gray-400 text-sm mb-1 flex items-center gap-1">
            <CheckCircle className="w-4 h-4" />
            Correct
          </div>
          <div className="text-3xl font-bold text-green-400">{currentMetrics.correct}</div>
          <div className="text-xs text-gray-500 mt-1">
            {currentMetrics.total_verified > 0
              ? ((currentMetrics.correct / currentMetrics.total_verified) * 100).toFixed(1)
              : 0}
            % win rate
          </div>
        </div>

        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/30">
          <div className="text-gray-400 text-sm mb-1 flex items-center gap-1">
            <XCircle className="w-4 h-4" />
            Incorrect
          </div>
          <div className="text-3xl font-bold text-red-400">{currentMetrics.incorrect}</div>
          <div className="text-xs text-gray-500 mt-1">
            {currentMetrics.total_verified > 0
              ? ((currentMetrics.incorrect / currentMetrics.total_verified) * 100).toFixed(1)
              : 0}
            % miss rate
          </div>
        </div>
      </div>

      {/* Accuracy Trend Chart */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Accuracy Trend</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#4B5563" opacity={0.5} />
            <XAxis dataKey="name" stroke="#9CA3AF" />
            <YAxis stroke="#9CA3AF" domain={[0, 100]} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#F3F4F6' }}
            />
            <Bar dataKey="accuracy" radius={[8, 8, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.accuracy >= 60 ? '#10B981' : entry.accuracy >= 55 ? '#F59E0B' : '#EF4444'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Public Ledger */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-6 h-6 text-purple-400" />
          <h3 className="text-lg font-semibold text-white">Public Accuracy Ledger</h3>
        </div>
        <p className="text-sm text-gray-400 mb-4">
          Top 10 most accurate high-confidence forecasts from the past 7 days
          <span className="block text-xs text-gray-500 mt-1">⏰ Updates nightly after games resolve</span>
        </p>

        {publicLedger.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            No verified forecasts available yet. Check back after games complete.
          </div>
        ) : (
          <div className="space-y-2">
            {publicLedger.map((entry, index) => (
              <div
                key={index}
                className="flex items-center justify-between bg-gray-900/50 rounded-lg p-4 border border-gray-700 hover:border-purple-500/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-purple-600 text-white font-bold text-sm">
                    #{index + 1}
                  </div>
                  <div>
                    <div className="text-white font-semibold">{entry.creator_name}</div>
                    <div className="text-sm text-gray-400">{entry.event}</div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-white font-semibold">{entry.forecast}</div>
                    <div className="text-sm text-gray-400">
                      {(entry.confidence * 100).toFixed(0)}% confidence
                    </div>
                  </div>
                  <CheckCircle className="w-6 h-6 text-green-400" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Transparency Notice */}
      <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/30">
        <div className="text-sm text-blue-300">
          <strong>🔒 Verification Process:</strong> All forecasts are automatically resolved within 24 hours
          of game completion. Results are pulled from official sports data APIs and stored immutably on our
          public ledger. This ensures complete transparency and accountability.
        </div>
      </div>
    </div>
  );
};

export default TrustLoop;
