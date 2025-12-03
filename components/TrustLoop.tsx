import React, { useEffect, useState } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

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
  overall?: {
    '7day_accuracy': number;
    '7day_record': string;
    '7day_units': number;
    '30day_roi': number;
    '30day_units': number;
    brier_score: number;
  };
  by_sport?: Record<string, {
    accuracy: number;
    roi: number;
    units: number;
    record: string;
    total_predictions: number;
  }>;
  confidence_calibration?: {
    high_confidence: { predicted: number; actual: number; count: number };
    medium_confidence: { predicted: number; actual: number; count: number };
    low_confidence: { predicted: number; actual: number; count: number };
  };
  recent_performance?: Array<{
    event_id: string;
    game: string;
    sport: string;
    prediction: string;
    result: string;
    units: number;
    confidence: number;
    graded_at: string;
  }>;
  yesterday?: {
    record: string;
    units: number;
    accuracy: number;
    message: string;
  };
}

interface TrendData {
  date: string;
  accuracy: number;
  units: number;
  wins: number;
  losses: number;
}

interface HistoryEntry {
  event_id: string;
  game: string;
  sport: string;
  prediction: string;
  result: string;
  units: number;
  confidence: number;
  graded_at: string;
}

const TrustLoop: React.FC = () => {
  const [metrics, setMetrics] = useState<TrustMetrics | null>(null);
  const [trend, setTrend] = useState<TrendData[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSport, setSelectedSport] = useState<string>('all');

  useEffect(() => {
    loadTrustData();
    // Refresh every 5 minutes
    const interval = setInterval(loadTrustData, 300000);
    return () => clearInterval(interval);
  }, []);

  const loadTrustData = async () => {
    try {
      setLoading(true);

      // Fetch Phase 17 metrics (7-day accuracy, 30-day ROI, Brier Score, by_sport, yesterday)
      const metricsResponse = await fetch('http://localhost:8000/api/trust/metrics');
      if (metricsResponse.ok) {
        const metricsData = await metricsResponse.json();
        setMetrics(metricsData);
      }

      // Fetch 7-day accuracy trend for sparkline
      const trendResponse = await fetch('http://localhost:8000/api/trust/trend?days=7');
      if (trendResponse.ok) {
        const trendData = await trendResponse.json();
        setTrend(trendData);
      }

      // Fetch recent graded predictions (last 20)
      const historyResponse = await fetch('http://localhost:8000/api/trust/history?days=7&limit=20');
      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        // API returns {count: X, predictions: [...]}
        setHistory(Array.isArray(historyData) ? historyData : historyData.predictions || []);
      }
    } catch (error) {
      console.error('Failed to load Phase 17 trust data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Extract metrics safely
  const accuracy7Day = metrics?.overall?.['7day_accuracy'] || 0;
  const roi30Day = metrics?.overall?.['30day_roi'] || 0;
  const brierScore = metrics?.overall?.brier_score || 0;
  const record7Day = metrics?.overall?.['7day_record'] || '0-0';
  const units7Day = metrics?.overall?.['7day_units'] || 0;
  const yesterdayMessage = metrics?.yesterday?.message || 'No games graded yet';

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

      {/* Yesterday's Performance Hero */}
      {metrics?.yesterday && (
        <div className="bg-gradient-to-r from-green-900/20 to-emerald-900/20 rounded-lg p-6 border border-green-500/30">
          <div className="flex items-center gap-3 mb-2">
            <Award className="w-6 h-6 text-green-400" />
            <h3 className="text-xl font-bold text-white">Yesterday's Performance</h3>
          </div>
          <p className="text-2xl font-bold text-green-400">{yesterdayMessage}</p>
          <div className="text-sm text-gray-400 mt-2">
            Record: {metrics.yesterday.record} | Units: {metrics.yesterday.units >= 0 ? '+' : ''}{metrics.yesterday.units.toFixed(2)} | Accuracy: {(metrics.yesterday.accuracy * 100).toFixed(1)}%
          </div>
        </div>
      )}



      {/* Rolling Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className={`rounded-lg p-4 ${getAccuracyBgColor(accuracy7Day / 100)} border border-purple-500/30`}>
          <div className="text-gray-400 text-sm mb-1">7-Day Accuracy</div>
          <div className={`text-3xl font-bold ${getAccuracyColor(accuracy7Day / 100)}`}>
            {accuracy7Day.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Record: {record7Day}</div>
          <div className="text-xs text-gray-400 mt-2 leading-relaxed">
            Units: {units7Day >= 0 ? '+' : ''}{units7Day.toFixed(2)}
          </div>
        </div>

        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <div className="text-gray-400 text-sm mb-1">30-Day ROI</div>
          <div className={`text-3xl font-bold ${roi30Day >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {roi30Day >= 0 ? '+' : ''}{roi30Day.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Return on investment</div>
        </div>

        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/30">
          <div className="text-gray-400 text-sm mb-1">Brier Score</div>
          <div className="text-3xl font-bold text-green-400">{brierScore.toFixed(3)}</div>
          <div className="text-xs text-gray-500 mt-1">Calibration quality</div>
          <div className="text-xs text-gray-400 mt-2 leading-relaxed">
            Lower is better (0.0 = perfect)
          </div>
        </div>

        <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/30">
          <div className="text-gray-400 text-sm mb-1">Total Sports</div>
          <div className="text-3xl font-bold text-blue-400">{Object.keys(metrics?.by_sport || {}).length}</div>
          <div className="text-xs text-gray-500 mt-1">NBA, NFL, MLB, NHL, NCAAB, NCAAF</div>
        </div>
      </div>

      {/* 7-Day Accuracy Sparkline */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">7-Day Accuracy Trend</h3>
        {trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#4B5563" opacity={0.5} />
              <XAxis dataKey="date" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" domain={[0, 100]} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#F3F4F6' }}
              />
              <Line type="monotone" dataKey="accuracy" stroke="#D4A64A" strokeWidth={3} dot={{ fill: '#D4A64A', r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-8 text-gray-400">No trend data available yet</div>
        )}
      </div>

      {/* Recent Graded Predictions */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-6 h-6 text-purple-400" />
          <h3 className="text-lg font-semibold text-white">Recent Graded Predictions</h3>
        </div>
        <p className="text-sm text-gray-400 mb-4">
          Last 20 graded predictions from the past 7 days
          <span className="block text-xs text-gray-500 mt-1">⏰ Auto-graded daily at 4:15 AM EST</span>
        </p>

        {history.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            No graded predictions available yet. Check back after games complete.
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((entry, index) => (
              <div
                key={index}
                className={`flex items-center justify-between rounded-lg p-4 border transition-colors ${
                  entry.result === 'WIN'
                    ? 'bg-green-900/20 border-green-500/30 hover:border-green-500/50'
                    : entry.result === 'LOSS'
                    ? 'bg-red-900/20 border-red-500/30 hover:border-red-500/50'
                    : 'bg-gray-900/50 border-gray-700 hover:border-gray-500'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-700 text-white font-bold text-xs">
                    {entry.sport}
                  </div>
                  <div>
                    <div className="text-white font-semibold">{entry.game}</div>
                    <div className="text-sm text-gray-400">{entry.prediction}</div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className={`text-lg font-bold ${
                      entry.result === 'WIN' ? 'text-green-400' : entry.result === 'LOSS' ? 'text-red-400' : 'text-gray-400'
                    }`}>
                      {entry.result}
                    </div>
                    <div className="text-sm text-gray-400">
                      {entry.units >= 0 ? '+' : ''}{entry.units.toFixed(2)} units | {(entry.confidence * 100).toFixed(0)}% confidence
                    </div>
                  </div>
                  {entry.result === 'WIN' ? (
                    <CheckCircle className="w-6 h-6 text-green-400" />
                  ) : entry.result === 'LOSS' ? (
                    <XCircle className="w-6 h-6 text-red-400" />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-gray-600" />
                  )}
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
