import React, { useEffect, useState } from 'react';

export interface CLVDataPoint {
  event_id: string;
  pick_date: string;
  sport: string;
  team: string;
  predicted_prob: number;
  market_prob: number;
  clv: number;
  outcome?: 'win' | 'loss' | 'pending';
}

export interface CLVStats {
  average_clv: number;
  total_picks: number;
  positive_clv_picks: number;
  clv_trend: 'improving' | 'declining' | 'stable';
  last_30_days_avg: number;
}

interface CLVTrackerProps {
  userId: string;
  userTier: 'starter' | 'pro' | 'sharps_room' | 'founder';
}

const CLVTracker: React.FC<CLVTrackerProps> = ({ userId, userTier }) => {
  const [clvData, setCLVData] = useState<CLVDataPoint[]>([]);
  const [stats, setStats] = useState<CLVStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const hasProAccess = ['pro', 'sharps_room', 'founder'].includes(userTier);

  useEffect(() => {
    if (!hasProAccess) return;

    const fetchCLVData = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem('token');
        const response = await fetch(`/api/performance/clv?user_id=${userId}&range=${timeRange}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        
        if (!response.ok) throw new Error('Failed to fetch CLV data');
        
        const data = await response.json();
        setCLVData(data.picks || []);
        setStats(data.stats || null);
      } catch (error) {
        console.error('Error fetching CLV data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCLVData();
  }, [userId, timeRange, hasProAccess]);

  // Transform data for chart
  const chartData = clvData.map((point, index) => ({
    name: new Date(point.pick_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    clv: (point.clv * 100).toFixed(2),
    cumulative: (
      clvData.slice(0, index + 1).reduce((sum, p) => sum + p.clv, 0) / (index + 1) * 100
    ).toFixed(2),
  }));

  if (!hasProAccess) {
    return (
      <div className="bg-charcoal rounded-xl p-8 text-center space-y-4">
        <div className="w-16 h-16 bg-electric-blue/20 rounded-full flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-electric-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h3 className="text-xl font-bold">CLV Tracking: Pro Feature</h3>
        <p className="text-light-gray max-w-md mx-auto">
          Closing Line Value (CLV) is the ultimate measure of your picks' quality. Track your edge against the market.
        </p>
        <div className="bg-navy rounded-lg p-4 max-w-sm mx-auto text-left space-y-2">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">Pick-by-pick CLV analysis</span>
          </div>
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">Cumulative CLV tracking</span>
          </div>
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-neon-green" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            <span className="text-sm">Trend analysis & insights</span>
          </div>
        </div>
        <button className="bg-electric-blue text-white px-6 py-3 rounded-lg font-semibold hover:bg-electric-blue/90 transition">
          Upgrade to Pro
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-charcoal rounded-xl p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-electric-blue border-t-transparent"></div>
      </div>
    );
  }

  if (!stats || clvData.length === 0) {
    return (
      <div className="bg-charcoal rounded-xl p-8 text-center space-y-4">
        <p className="text-light-gray">No CLV data available yet. Start making picks to track your edge!</p>
      </div>
    );
  }

  const positiveCLVPercentage = ((stats.positive_clv_picks / stats.total_picks) * 100).toFixed(1);

  return (
    <div className="bg-charcoal rounded-xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold">Closing Line Value (CLV) Tracker</h3>
          <p className="text-sm text-light-gray">
            Measure your edge against the market's final assessment
          </p>
        </div>
        <div className="flex space-x-2">
          {(['7d', '30d', '90d', 'all'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
                timeRange === range
                  ? 'bg-electric-blue text-white'
                  : 'bg-navy text-light-gray hover:bg-navy/70'
              }`}
            >
              {range === 'all' ? 'All Time' : range.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid md:grid-cols-4 gap-4">
        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Average CLV</div>
          <div className={`text-2xl font-bold ${stats.average_clv > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
            {stats.average_clv > 0 ? '+' : ''}{(stats.average_clv * 100).toFixed(2)}%
          </div>
          <div className="text-xs text-light-gray mt-1">
            Target: +3.0% or higher
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Total Picks</div>
          <div className="text-2xl font-bold">{stats.total_picks}</div>
          <div className="text-xs text-light-gray mt-1">
            {stats.positive_clv_picks} positive CLV
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Positive CLV Rate</div>
          <div className="text-2xl font-bold text-electric-blue">{positiveCLVPercentage}%</div>
          <div className="text-xs text-light-gray mt-1">
            Target: 60%+ hit rate
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4">
          <div className="text-sm text-light-gray mb-1">Trend</div>
          <div className={`text-2xl font-bold flex items-center ${
            stats.clv_trend === 'improving' ? 'text-neon-green' :
            stats.clv_trend === 'declining' ? 'text-bold-red' : 'text-gold'
          }`}>
            {stats.clv_trend === 'improving' && '↑'}
            {stats.clv_trend === 'declining' && '↓'}
            {stats.clv_trend === 'stable' && '→'}
            <span className="ml-2 text-lg capitalize">{stats.clv_trend}</span>
          </div>
          <div className="text-xs text-light-gray mt-1">
            Last 30d: {(stats.last_30_days_avg * 100).toFixed(2)}%
          </div>
        </div>
      </div>

      {/* CLV Chart */}
      <div className="bg-navy rounded-lg p-4">
        <h4 className="font-semibold mb-4">CLV Over Time</h4>
        <div className="text-sm text-light-gray">
          Chart visualization requires recharts library. Install with: npm install recharts
        </div>
        {/* Chart implementation removed - add recharts library to enable */}
      </div>

      {/* Recent Picks Table */}
      <div className="bg-navy rounded-lg p-4">
        <h4 className="font-semibold mb-4">Recent Picks with CLV</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-light-gray border-b border-charcoal">
                <th className="pb-2">Date</th>
                <th className="pb-2">Sport</th>
                <th className="pb-2">Team</th>
                <th className="pb-2">Your Prob</th>
                <th className="pb-2">Market Prob</th>
                <th className="pb-2">CLV</th>
                <th className="pb-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {clvData.slice(0, 10).map((pick, index) => (
                <tr key={index} className="border-b border-charcoal/50">
                  <td className="py-2">
                    {new Date(pick.pick_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </td>
                  <td className="py-2 text-light-gray">{pick.sport}</td>
                  <td className="py-2 font-medium">{pick.team}</td>
                  <td className="py-2">{(pick.predicted_prob * 100).toFixed(1)}%</td>
                  <td className="py-2 text-light-gray">{(pick.market_prob * 100).toFixed(1)}%</td>
                  <td className={`py-2 font-semibold ${pick.clv > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                    {pick.clv > 0 ? '+' : ''}{(pick.clv * 100).toFixed(2)}%
                  </td>
                  <td className="py-2">
                    {pick.outcome === 'win' && <span className="text-neon-green">✓ Win</span>}
                    {pick.outcome === 'loss' && <span className="text-bold-red">✗ Loss</span>}
                    {pick.outcome === 'pending' && <span className="text-gold">⏱ Pending</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Educational Note */}
      <div className="bg-electric-blue/10 border border-electric-blue rounded-lg p-4">
        <h5 className="font-semibold text-electric-blue mb-2">What is CLV?</h5>
        <p className="text-sm text-light-gray">
          Closing Line Value measures the difference between your bet's price and the market's final assessment (closing line).
          Positive CLV indicates you're consistently beating the market—the #1 predictor of long-term profitability.
          Our target: +3% average CLV with 60%+ hit rate.
        </p>
      </div>
    </div>
  );
};

export default CLVTracker;
