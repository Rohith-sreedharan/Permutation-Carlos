import React, { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, TrendingDown, AlertTriangle, Target, Activity, Zap, Brain } from 'lucide-react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

interface BettingCommandCenterProps {
  onAuthError: () => void;
}

interface PnLMetrics {
  total_profit: number;
  total_stake: number;
  roi: number;
  win_rate: number;
  chase_index: number;
  total_bets: number;
  wins: number;
  losses: number;
  warning?: string;
}

interface EdgeAnalysis {
  total_conflicts: number;
  total_aligned: number;
  ev_lost: number;
  coaching_message: string;
  conflict_details: Array<{
    user_pick: string;
    model_pick: string;
    ev_cost: number;
    message: string;
  }>;
}

interface BetHistory {
  _id: string;
  selection: string;
  stake: number;
  odds: number;
  outcome: string;
  profit?: number;
  created_at: string;
  sport: string;
}

const BettingCommandCenter: React.FC<BettingCommandCenterProps> = ({ onAuthError }) => {
  const [pnl, setPnl] = useState<PnLMetrics | null>(null);
  const [edgeAnalysis, setEdgeAnalysis] = useState<EdgeAnalysis | null>(null);
  const [recentBets, setRecentBets] = useState<BetHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [tiltLevel, setTiltLevel] = useState(0); // 0-100

  useEffect(() => {
    loadBettingData();
    
    // Refresh every 30 seconds
    const interval = setInterval(loadBettingData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadBettingData = async () => {
    try {
      const token = localStorage.getItem('authToken');
      
      if (!token) {
        onAuthError();
        return;
      }

      // Fetch PnL metrics
      const pnlRes = await fetch(`${API_BASE_URL}/api/bets/pnl?days=30`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (pnlRes.ok) {
        const pnlData = await pnlRes.json();
        setPnl(pnlData);
        
        // Calculate tilt level from chase index
        const tilt = Math.min(100, (pnlData.chase_index - 1) * 50);
        setTiltLevel(Math.max(0, tilt));
      }

      // Fetch edge analysis
      const edgeRes = await fetch(`${API_BASE_URL}/api/edge-analysis?days=7`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (edgeRes.ok) {
        const edgeData = await edgeRes.json();
        setEdgeAnalysis(edgeData);
      }

      // Fetch recent bets
      const betsRes = await fetch(`${API_BASE_URL}/api/bets/history?limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (betsRes.ok) {
        const betsData = await betsRes.json();
        setRecentBets(betsData.bets || []);
      }

      setLoading(false);
    } catch (error) {
      console.error('Failed to load betting data:', error);
      setLoading(false);
    }
  };

  const getTiltColor = () => {
    if (tiltLevel < 30) return '#10B981'; // Green
    if (tiltLevel < 70) return '#F59E0B'; // Yellow
    return '#EF4444'; // Red
  };

  const getTiltLabel = () => {
    if (tiltLevel < 30) return 'Disciplined';
    if (tiltLevel < 70) return 'Warning';
    return '🚨 TILTING';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0C1018]">
        <div className="text-[#D4A64A] text-xl">Loading Betting Command Center...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0C1018] p-6 space-y-6">
      {/* Header */}
      <div className="bg-linear-to-r from-[#1A1F27] via-[#0C1018] to-[#1A1F27] rounded-lg p-6 border border-[#D4A64A]/20">
        <div className="flex items-center gap-3 mb-2">
          <Target className="w-8 h-8 text-[#D4A64A]" />
          <h1 className="text-3xl font-bold text-white">Betting Command Center</h1>
        </div>
        <p className="text-gray-400 text-sm">
          Track your bets, analyze your edge, and get AI coaching to beat the books
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* PnL Card */}
        <div className="bg-linear-to-br from-[#1A1F27] to-[#0C1018] rounded-lg p-5 border border-[#D4A64A]/30">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {pnl && pnl.total_profit >= 0 ? (
                <TrendingUp className="w-5 h-5 text-[#10B981]" />
              ) : (
                <TrendingDown className="w-5 h-5 text-[#A03333]" />
              )}
              <div className="text-sm text-gray-400">Net PnL (30d)</div>
            </div>
          </div>
          <div className={`text-3xl font-bold ${pnl && pnl.total_profit >= 0 ? 'text-[#10B981]' : 'text-[#A03333]'}`}>
            {pnl ? `$${pnl.total_profit.toFixed(2)}` : '$0.00'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {pnl?.total_bets || 0} bets tracked
          </div>
        </div>

        {/* ROI Card */}
        <div className="bg-linear-to-br from-[#1A1F27] to-[#0C1018] rounded-lg p-5 border border-[#D4A64A]/30">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-[#D4A64A]" />
            <div className="text-sm text-gray-400">ROI</div>
          </div>
          <div className={`text-3xl font-bold ${pnl && pnl.roi >= 0 ? 'text-[#10B981]' : 'text-[#A03333]'}`}>
            {pnl ? `${pnl.roi.toFixed(1)}%` : '0%'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Win Rate: {pnl?.win_rate.toFixed(1) || 0}%
          </div>
        </div>

        {/* Tilt Meter */}
        <div className="bg-linear-to-br from-[#1A1F27] to-[#0C1018] rounded-lg p-5 border border-[#D4A64A]/30">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5" style={{ color: getTiltColor() }} />
            <div className="text-sm text-gray-400">Tilt Meter</div>
          </div>
          <div className="text-3xl font-bold" style={{ color: getTiltColor() }}>
            {getTiltLabel()}
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
            <div
              className="h-2 rounded-full transition-all duration-500"
              style={{ 
                width: `${tiltLevel}%`,
                backgroundColor: getTiltColor()
              }}
            />
          </div>
          {pnl?.warning && (
            <div className="text-xs text-[#A03333] mt-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {pnl.warning}
            </div>
          )}
        </div>

        {/* Edge Analysis */}
        <div className="bg-linear-to-br from-[#1A1F27] to-[#0C1018] rounded-lg p-5 border border-[#D4A64A]/30">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-5 h-5 text-[#8B5CF6]" />
            <div className="text-sm text-gray-400">AI Edge</div>
          </div>
          <div className="text-3xl font-bold text-[#8B5CF6]">
            {edgeAnalysis ? `${edgeAnalysis.total_aligned}/${edgeAnalysis.total_aligned + edgeAnalysis.total_conflicts}` : '0/0'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Aligned with model
          </div>
        </div>
      </div>

      {/* Edge Analysis Coaching */}
      {edgeAnalysis && edgeAnalysis.coaching_message && (
        <div className={`rounded-lg p-4 border ${
          edgeAnalysis.total_conflicts > edgeAnalysis.total_aligned
            ? 'bg-[#A03333]/10 border-[#A03333]/30'
            : 'bg-[#10B981]/10 border-[#10B981]/30'
        }`}>
          <div className="flex items-start gap-3">
            {edgeAnalysis.total_conflicts > edgeAnalysis.total_aligned ? (
              <AlertTriangle className="w-5 h-5 text-[#A03333] mt-0.5" />
            ) : (
              <Zap className="w-5 h-5 text-[#10B981] mt-0.5" />
            )}
            <div>
              <div className="font-bold text-white mb-1">AI Coach Says:</div>
              <div className="text-gray-300 text-sm">{edgeAnalysis.coaching_message}</div>
              {edgeAnalysis.ev_lost > 0 && (
                <div className="text-[#A03333] text-xs mt-2">
                  Fighting the model cost you ~${edgeAnalysis.ev_lost.toFixed(2)} in expected value
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Recent Bets Table */}
      <div className="bg-[#1A1F27] rounded-lg p-6 border border-[#D4A64A]/20">
        <h2 className="text-xl font-bold text-white mb-4">Recent Bets</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 pb-2 pr-4">Date</th>
                <th className="text-left text-gray-400 pb-2 pr-4">Selection</th>
                <th className="text-left text-gray-400 pb-2 pr-4">Stake</th>
                <th className="text-left text-gray-400 pb-2 pr-4">Odds</th>
                <th className="text-left text-gray-400 pb-2 pr-4">Outcome</th>
                <th className="text-right text-gray-400 pb-2">Profit</th>
              </tr>
            </thead>
            <tbody>
              {recentBets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-gray-500 py-8">
                    No bets tracked yet. Start logging your bets manually or connect SharpSports.
                  </td>
                </tr>
              ) : (
                recentBets.map((bet) => (
                  <tr key={bet._id} className="border-b border-gray-800 hover:bg-[#0C1018]/50">
                    <td className="py-3 pr-4 text-gray-400">
                      {new Date(bet.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 pr-4 text-white font-medium">{bet.selection}</td>
                    <td className="py-3 pr-4 text-gray-300">${bet.stake}</td>
                    <td className="py-3 pr-4 text-gray-300">{bet.odds.toFixed(2)}</td>
                    <td className="py-3 pr-4">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        bet.outcome === 'win' ? 'bg-[#10B981]/20 text-[#10B981]' :
                        bet.outcome === 'loss' ? 'bg-[#A03333]/20 text-[#A03333]' :
                        'bg-gray-700 text-gray-400'
                      }`}>
                        {bet.outcome.toUpperCase()}
                      </span>
                    </td>
                    <td className={`py-3 text-right font-bold ${
                      bet.profit && bet.profit > 0 ? 'text-[#10B981]' :
                      bet.profit && bet.profit < 0 ? 'text-[#A03333]' :
                      'text-gray-400'
                    }`}>
                      {bet.profit ? `$${bet.profit.toFixed(2)}` : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default BettingCommandCenter;
