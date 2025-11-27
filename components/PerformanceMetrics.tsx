import React, { useEffect, useState } from 'react';

export interface PerformanceMetrics {
  brier_score: number;
  log_loss: number;
  roi: number;
  clv: number;
  total_picks: number;
  winning_picks: number;
  win_rate: number;
  avg_odds: number;
  profit_loss: number;
  market_breakdown: {
    [sport: string]: {
      picks: number;
      win_rate: number;
      roi: number;
      clv: number;
    };
  };
}

interface PerformanceMetricsProps {
  userId: string;
  userTier: 'starter' | 'pro' | 'sharps_room' | 'founder';
}

const PerformanceMetricsDashboard: React.FC<PerformanceMetricsProps> = ({ userId, userTier }) => {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'season'>('30d');

  const hasSharpsAccess = ['sharps_room', 'founder'].includes(userTier);

  useEffect(() => {
    if (!hasSharpsAccess) return;

    const fetchPerformanceMetrics = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('token');
        const response = await fetch(`/api/performance/report?user_id=${userId}&range=${timeRange}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        
        if (!response.ok) throw new Error('Failed to fetch performance metrics');
        
        const data = await response.json();
        setMetrics(data);
      } catch (error) {
        console.error('Error fetching performance metrics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPerformanceMetrics();
  }, [userId, timeRange, hasSharpsAccess]);

  if (!hasSharpsAccess) {
    return (
      <div className="bg-charcoal rounded-xl p-8 text-center space-y-4">
        <div className="w-16 h-16 bg-gold/20 rounded-full flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h3 className="text-xl font-bold">Advanced Performance Metrics: Sharps Room Exclusive</h3>
        <p className="text-light-gray max-w-md mx-auto">
          Deep dive into probabilistic accuracy with Brier Score, Log Loss, and market-by-market performance analytics.
        </p>
        <div className="bg-navy rounded-lg p-4 max-w-sm mx-auto text-left space-y-2">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">Brier Score & Log Loss tracking</span>
          </div>
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">Market-by-market breakdowns</span>
          </div>
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">ROI & CLV comparison charts</span>
          </div>
        </div>
        <button className="bg-gold text-charcoal px-6 py-3 rounded-lg font-semibold hover:bg-gold/90 transition">
          Upgrade to Sharps Room
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-charcoal rounded-xl p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-gold border-t-transparent"></div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="bg-charcoal rounded-xl p-8 text-center space-y-4">
        <p className="text-light-gray">No performance data available yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-charcoal rounded-xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold">Performance Analytics Dashboard</h3>
          <p className="text-sm text-light-gray">
            Probabilistic accuracy and profitability metrics
          </p>
        </div>
        <div className="flex space-x-2">
          {(['7d', '30d', '90d', 'season'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
                timeRange === range
                  ? 'bg-gold text-charcoal'
                  : 'bg-navy text-light-gray hover:bg-navy/70'
              }`}
            >
              {range === 'season' ? 'Season' : range.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Core Metrics Grid */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Brier Score</div>
          <div className={`text-2xl font-bold ${metrics.brier_score < 0.20 ? 'text-neon-green' : metrics.brier_score < 0.25 ? 'text-gold' : 'text-bold-red'}`}>
            {metrics.brier_score.toFixed(4)}
          </div>
          <div className="text-xs text-light-gray mt-1">
            Target: &lt;0.20 (Elite)
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Log Loss</div>
          <div className={`text-2xl font-bold ${metrics.log_loss < 0.60 ? 'text-neon-green' : metrics.log_loss < 0.70 ? 'text-gold' : 'text-bold-red'}`}>
            {metrics.log_loss.toFixed(4)}
          </div>
          <div className="text-xs text-light-gray mt-1">
            Target: &lt;0.60 (Elite)
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">ROI</div>
          <div className={`text-2xl font-bold ${metrics.roi > 8 ? 'text-neon-green' : metrics.roi > 0 ? 'text-electric-blue' : 'text-bold-red'}`}>
            {metrics.roi > 0 ? '+' : ''}{metrics.roi.toFixed(2)}%
          </div>
          <div className="text-xs text-light-gray mt-1">
            Target: +8.0% or higher
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">CLV</div>
          <div className={`text-2xl font-bold ${metrics.clv > 3 ? 'text-neon-green' : metrics.clv > 0 ? 'text-electric-blue' : 'text-bold-red'}`}>
            {metrics.clv > 0 ? '+' : ''}{metrics.clv.toFixed(2)}%
          </div>
          <div className="text-xs text-light-gray mt-1">
            Target: +3.0% or higher
          </div>
        </div>
      </div>

      {/* Performance Overview */}
      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Total Picks</div>
          <div className="text-2xl font-bold">{metrics.total_picks}</div>
          <div className="text-xs text-light-gray mt-1">
            {metrics.winning_picks} winners
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Win Rate</div>
          <div className={`text-2xl font-bold ${metrics.win_rate > 55 ? 'text-neon-green' : metrics.win_rate > 50 ? 'text-electric-blue' : 'text-light-gray'}`}>
            {metrics.win_rate.toFixed(1)}%
          </div>
          <div className="text-xs text-light-gray mt-1">
            Avg odds: {metrics.avg_odds > 0 ? '+' : ''}{metrics.avg_odds.toFixed(0)}
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Profit/Loss</div>
          <div className={`text-2xl font-bold ${metrics.profit_loss > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
            {metrics.profit_loss > 0 ? '+' : ''}${metrics.profit_loss.toFixed(2)}
          </div>
          <div className="text-xs text-light-gray mt-1">
            {metrics.profit_loss > 0 ? 'In profit' : 'Total loss'}
          </div>
        </div>
      </div>

      {/* Market Breakdown */}
      <div className="bg-navy rounded-lg p-4">
        <h4 className="font-semibold mb-4">Market Breakdown</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-light-gray border-b border-charcoal">
                <th className="pb-2">Sport</th>
                <th className="pb-2">Picks</th>
                <th className="pb-2">Win Rate</th>
                <th className="pb-2">ROI</th>
                <th className="pb-2">CLV</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.market_breakdown).map(([sport, data]) => {
                const marketData = data as { picks: number; win_rate: number; roi: number; clv: number };
                return (
                  <tr key={sport} className="border-b border-charcoal/50">
                    <td className="py-2 font-medium">{sport.toUpperCase()}</td>
                    <td className="py-2 text-light-gray">{marketData.picks}</td>
                    <td className={`py-2 ${marketData.win_rate > 55 ? 'text-neon-green' : 'text-light-gray'}`}>
                      {marketData.win_rate.toFixed(1)}%
                    </td>
                    <td className={`py-2 font-semibold ${marketData.roi > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                      {marketData.roi > 0 ? '+' : ''}{marketData.roi.toFixed(2)}%
                    </td>
                    <td className={`py-2 ${marketData.clv > 0 ? 'text-electric-blue' : 'text-light-gray'}`}>
                      {marketData.clv > 0 ? '+' : ''}{marketData.clv.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Metric Explanations */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-electric-blue/10 border border-electric-blue rounded-lg p-4">
          <h5 className="font-semibold text-electric-blue mb-2">📊 Brier Score</h5>
          <p className="text-sm text-light-gray">
            Measures probabilistic accuracy. Scores closer to 0 are better. Elite handicappers achieve &lt;0.20.
            Lower scores indicate your predicted probabilities match actual outcomes.
          </p>
        </div>
        <div className="bg-electric-blue/10 border border-electric-blue rounded-lg p-4">
          <h5 className="font-semibold text-electric-blue mb-2">📉 Log Loss</h5>
          <p className="text-sm text-light-gray">
            Penalizes confident incorrect predictions heavily. Scores below 0.60 indicate elite calibration.
            Essential for understanding how well your confidence matches reality.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PerformanceMetricsDashboard;
