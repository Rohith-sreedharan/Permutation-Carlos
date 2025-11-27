import React, { useState, useEffect } from 'react';
import { fetchCLVData, fetchPerformanceReport, getUserTier } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';

interface CLVData {
  picks: Array<{
    event_id: string;
    pick_type: string;
    clv: number;
    timestamp: string;
  }>;
  stats: {
    average_clv: number;
    total_picks: number;
    positive_clv_picks: number;
    clv_trend: string;
    last_30_days_avg: number;
  };
}

interface PerformanceData {
  brier_score: number;
  log_loss: number;
  roi: number;
  clv: number;
  total_picks: number;
  winning_picks: number;
  win_rate: number;
  avg_odds: number;
  profit_loss: number;
  market_breakdown: Record<string, any>;
}

const SharpsRoom: React.FC = () => {
  const [clvData, setCLVData] = useState<CLVData | null>(null);
  const [perfData, setPerfData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');
  const [error, setError] = useState<string | null>(null);
  const [userTier, setUserTier] = useState<string | null>(null);
  const [showUpgradeCTA, setShowUpgradeCTA] = useState(false);

  useEffect(() => {
    loadData();
  }, [timeRange]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [tierInfo, clv, perf] = await Promise.all([
        getUserTier(),
        fetchCLVData(timeRange as '7d' | '30d' | '90d' | 'all'),
        fetchPerformanceReport(timeRange as '7d' | '30d' | '90d' | 'season')
      ]);
      setUserTier(tierInfo.tier);
      
      // Check if user has access to Sharps Room
      if (tierInfo.tier !== 'sharps_room' && tierInfo.tier !== 'founder') {
        setShowUpgradeCTA(true);
      }
      
      setCLVData(clv as any); // CLVData type mismatch - backend returns different structure
      setPerfData(perf);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load Sharps Room data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgradeClick = async () => {
    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:8000/api/payment/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          tier_id: 'sharps_room',
          user_id: token ? JSON.parse(atob(token.split('.')[1])).sub : undefined
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const data = await response.json();
      
      // Redirect to Stripe checkout
      window.location.href = data.checkout_url;
    } catch (err) {
      console.error('Checkout error:', err);
      alert('Failed to start checkout. Please try again.');
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-center text-bold-red p-8">{error}</div>;
  if (!clvData || !perfData) return <div className="text-center text-white p-8">No data available</div>;

  // Process CLV data for charts
  const clvTimeSeries = clvData.picks.slice(0, 30).map((pick, idx) => ({
    index: idx + 1,
    clv: pick.clv,
    date: new Date(pick.timestamp).toLocaleDateString()
  })).reverse();

  const clvDistribution = [
    { range: '< -5', count: clvData.picks.filter(p => p.clv < -5).length },
    { range: '-5 to -2', count: clvData.picks.filter(p => p.clv >= -5 && p.clv < -2).length },
    { range: '-2 to 0', count: clvData.picks.filter(p => p.clv >= -2 && p.clv < 0).length },
    { range: '0 to 2', count: clvData.picks.filter(p => p.clv >= 0 && p.clv < 2).length },
    { range: '2 to 5', count: clvData.picks.filter(p => p.clv >= 2 && p.clv < 5).length },
    { range: '> 5', count: clvData.picks.filter(p => p.clv >= 5).length },
  ];

  return (
    <div className="space-y-6 bg-[#0a0e1a] min-h-screen p-6 relative">
      {/* Upgrade CTA Overlay */}
      {showUpgradeCTA && (
        <div className="absolute inset-0 z-50 flex items-center justify-center backdrop-blur-lg bg-[#0a0e1a]/90">
          <div className="bg-gradient-to-br from-charcoal to-navy border-2 border-electric-blue rounded-2xl p-8 max-w-lg mx-4 text-center shadow-2xl">
            <div className="text-6xl mb-4">🔒</div>
            <h2 className="text-3xl font-bold text-white font-teko mb-4">SHARPS ROOM ACCESS REQUIRED</h2>
            <p className="text-light-gray mb-6">Unlock elite analytics, CLV tracking, and volatility indices available only to Sharps Room+ members.</p>
            <div className="space-y-3 mb-6 text-left">
              <div className="flex items-start space-x-3">
                <span className="text-electric-blue text-xl">✓</span>
                <span className="text-white">Real-time CLV tracking with closing line value analysis</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-electric-blue text-xl">✓</span>
                <span className="text-white">Brier Score & Log Loss calibration metrics</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-electric-blue text-xl">✓</span>
                <span className="text-white">Volatility Index showing team variance patterns</span>
              </div>
              <div className="flex items-start space-x-3">
                <span className="text-electric-blue text-xl">✓</span>
                <span className="text-white">Access to AI-powered sharp insights</span>
              </div>
            </div>
            <button 
              onClick={handleUpgradeClick}
              className="w-full bg-gradient-to-r from-electric-blue to-purple-600 text-white font-bold py-4 px-8 rounded-lg text-lg hover:shadow-lg hover:shadow-electric-blue/50 transition-all"
            >
              UPGRADE TO SHARPS ROOM+
            </button>
            <button 
              onClick={() => window.location.href = '/dashboard'}
              className="mt-3 text-light-gray hover:text-white text-sm"
            >
              ← Back to Dashboard
            </button>
          </div>
        </div>
      )}
      
      {/* Blur content if not premium */}
      <div className={showUpgradeCTA ? 'filter blur-md pointer-events-none' : ''}>
      {/* Header with Elite Badge */}
      <PageHeader title="🏆 Sharps Room">
        <div className="flex items-center space-x-4">
          <span className="bg-gradient-to-r from-electric-blue to-purple-600 text-white text-xs font-bold px-3 py-1 rounded-full">
            SHARPS ROOM+
          </span>
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-charcoal border border-navy rounded-lg px-4 py-2 text-white text-sm focus:ring-2 focus:ring-electric-blue"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="season">Season</option>
          </select>
        </div>
      </PageHeader>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Brier Score */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-electric-blue/20">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-light-gray text-sm uppercase tracking-wider">Brier Score</h3>
            <span className={`text-xs font-bold px-2 py-1 rounded ${perfData.brier_score < 0.20 ? 'bg-neon-green/20 text-neon-green' : 'bg-yellow-500/20 text-yellow-500'}`}>
              {perfData.brier_score < 0.20 ? 'ELITE' : 'GOOD'}
            </span>
          </div>
          <p className="text-4xl font-bold text-white font-teko">{perfData.brier_score.toFixed(3)}</p>
          <p className="text-xs text-light-gray mt-2">Target: &lt; 0.200</p>
        </div>

        {/* Log Loss */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-purple-500/20">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-light-gray text-sm uppercase tracking-wider">Log Loss</h3>
            <span className={`text-xs font-bold px-2 py-1 rounded ${perfData.log_loss < 0.60 ? 'bg-neon-green/20 text-neon-green' : 'bg-yellow-500/20 text-yellow-500'}`}>
              {perfData.log_loss < 0.60 ? 'SHARP' : 'IMPROVING'}
            </span>
          </div>
          <p className="text-4xl font-bold text-white font-teko">{perfData.log_loss.toFixed(3)}</p>
          <p className="text-xs text-light-gray mt-2">Target: &lt; 0.600</p>
        </div>

        {/* Average CLV */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-neon-green/20">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-light-gray text-sm uppercase tracking-wider">Average CLV</h3>
            <span className={`text-xs font-bold px-2 py-1 rounded ${clvData.stats.average_clv > 2 ? 'bg-neon-green/20 text-neon-green' : 'bg-bold-red/20 text-bold-red'}`}>
              {clvData.stats.clv_trend.toUpperCase()}
            </span>
          </div>
          <p className="text-4xl font-bold text-neon-green font-teko">+{clvData.stats.average_clv.toFixed(2)}</p>
          <p className="text-xs text-light-gray mt-2">{clvData.stats.positive_clv_picks}/{clvData.stats.total_picks} positive CLV</p>
        </div>

        {/* ROI */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-yellow-500/20">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-light-gray text-sm uppercase tracking-wider">ROI</h3>
            <span className={`text-xs font-bold px-2 py-1 rounded ${perfData.roi > 8 ? 'bg-neon-green/20 text-neon-green' : 'bg-gray-500/20 text-gray-400'}`}>
              {perfData.roi > 8 ? 'WINNING' : 'TRACKING'}
            </span>
          </div>
          <p className="text-4xl font-bold text-white font-teko">{perfData.roi > 0 ? '+' : ''}{perfData.roi.toFixed(1)}%</p>
          <p className="text-xs text-light-gray mt-2">Target: &gt; 8%</p>
        </div>
      </div>

      {/* CLV Time Series Chart */}
      <div className={`bg-charcoal rounded-xl p-6 border border-navy ${showUpgradeCTA ? 'filter blur-md' : ''}`}>
        <h3 className="text-xl font-bold text-white font-teko mb-4">📈 CLV History (Last 30 Picks)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={clvTimeSeries}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a2332" />
            <XAxis dataKey="date" stroke="#7b8a9d" tick={{ fontSize: 12 }} />
            <YAxis stroke="#7b8a9d" tick={{ fontSize: 12 }} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#0f1419', border: '1px solid #00CFFF', borderRadius: '8px' }}
              labelStyle={{ color: '#00CFFF' }}
              itemStyle={{ color: '#fff' }}
            />
            <Legend wrapperStyle={{ color: '#7b8a9d' }} />
            <ReferenceLine y={0} stroke="#7b8a9d" strokeDasharray="3 3" />
            <Line 
              type="monotone" 
              dataKey="clv" 
              stroke="#00CFFF" 
              strokeWidth={2} 
              dot={{ fill: '#00CFFF', r: 4 }} 
              name="CLV (pts)"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* CLV Distribution */}
      <div className={`bg-charcoal rounded-xl p-6 border border-navy ${showUpgradeCTA ? 'filter blur-md' : ''}`}>
        <h3 className="text-xl font-bold text-white font-teko mb-4">📊 CLV Distribution</h3>
        <div className="space-y-2">
          {clvDistribution.map(item => (
            <div key={item.range} className="flex items-center justify-between">
              <span className="text-light-gray w-24">{item.range}</span>
              <div className="flex-1 mx-4">
                <div className="bg-navy rounded-full h-6">
                  <div 
                    className="bg-electric-blue rounded-full h-6 flex items-center justify-end pr-2"
                    style={{ width: `${(item.count / Math.max(...clvDistribution.map(d => d.count))) * 100}%` }}
                  >
                    <span className="text-white text-xs font-bold">{item.count}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Performance Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Win Rate & Stats */}
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <h3 className="text-xl font-bold text-white font-teko mb-4">🎯 Performance Stats</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-light-gray">Win Rate</span>
              <span className="text-white font-bold text-xl">{perfData.win_rate.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-light-gray">Total Picks</span>
              <span className="text-white font-bold text-xl">{perfData.total_picks}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-light-gray">Winning Picks</span>
              <span className="text-neon-green font-bold text-xl">{perfData.winning_picks}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-light-gray">Profit/Loss</span>
              <span className={`font-bold text-xl ${perfData.profit_loss >= 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                {perfData.profit_loss >= 0 ? '+' : ''}{perfData.profit_loss.toFixed(2)} units
              </span>
            </div>
          </div>
        </div>

        {/* Market Breakdown */}
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <h3 className="text-xl font-bold text-white font-teko mb-4">🏀 Market Breakdown</h3>
          <div className="space-y-3">
            {Object.entries(perfData.market_breakdown || {}).map(([sport, data]: [string, any]) => (
              <div key={sport} className="flex justify-between items-center">
                <span className="text-light-gray capitalize">{sport}</span>
                <div className="flex items-center space-x-2">
                  <span className="text-white font-semibold">{data.picks} picks</span>
                  <span className={`text-sm font-bold ${data.roi >= 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                    {data.roi >= 0 ? '+' : ''}{data.roi.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Elite Insights Panel */}
      <div className="bg-gradient-to-r from-electric-blue/10 to-purple-600/10 border border-electric-blue/30 rounded-xl p-6">
        <h3 className="text-xl font-bold text-white font-teko mb-3 flex items-center">
          <span className="mr-2">💡</span>
          Sharp Insights
        </h3>
        <div className="space-y-2 text-sm text-light-gray">
          <p>• Your Brier Score of {perfData.brier_score.toFixed(3)} {perfData.brier_score < 0.20 ? 'ranks in the elite tier' : 'shows room for calibration improvement'}.</p>
          <p>• Average CLV of +{clvData.stats.average_clv.toFixed(2)} indicates {clvData.stats.average_clv > 2 ? 'strong line-shopping skills' : 'potential for better timing'}.</p>
          <p>• {clvData.stats.clv_trend === 'improving' ? '📈 Your CLV trend is improving - keep it up!' : clvData.stats.clv_trend === 'worsening' ? '⚠️ CLV declining - review your entry timing' : '➡️ CLV stable - focus on volume'}</p>
        </div>
      </div>
      </div>
    </div>
  );
};

export default SharpsRoom;
