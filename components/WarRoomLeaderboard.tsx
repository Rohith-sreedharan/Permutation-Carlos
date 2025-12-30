import React, { useState, useEffect } from 'react';
import { TrendingUp, Award, CheckCircle, Zap } from 'lucide-react';
import PageHeader from './PageHeader';
import LoadingSpinner from './LoadingSpinner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface LeaderboardEntry {
  user_id: string;
  username: string;
  rank: string;
  units?: number;
  win_rate?: number;
  sample_size: number;
  volatility_adjusted_score: number;
  max_drawdown?: number;
  template_compliance_pct: number;
  has_verified_track_record: boolean;
  badges: string[];
  leaderboard_position: number;
}

const WarRoomLeaderboard: React.FC = () => {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<'score' | 'win_rate' | 'compliance'>('score');

  useEffect(() => {
    loadLeaderboard();
  }, [sortBy]);

  const loadLeaderboard = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/war-room/leaderboard?limit=100`);
      const data = await response.json();
      setEntries(data.leaderboard);
      setLoading(false);
    } catch (err) {
      console.error('Failed to load leaderboard:', err);
      setLoading(false);
    }
  };

  const getRankColor = (rank: string) => {
    switch (rank) {
      case 'elite':
        return 'from-yellow-500 to-orange-500';
      case 'verified':
        return 'from-green-500 to-emerald-500';
      case 'contributor':
        return 'from-blue-500 to-cyan-500';
      default:
        return 'from-gray-500 to-slate-500';
    }
  };

  const getRankBgColor = (rank: string) => {
    switch (rank) {
      case 'elite':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'verified':
        return 'bg-green-500/20 text-green-400';
      case 'contributor':
        return 'bg-blue-500/20 text-blue-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  const getMedalIcon = (position: number) => {
    if (position === 1) return '🥇';
    if (position === 2) return '🥈';
    if (position === 3) return '🥉';
    return position;
  };

  if (loading) return <LoadingSpinner />;

  const sorted = [...entries].sort((a, b) => {
    if (sortBy === 'win_rate') {
      return (b.win_rate || 0) - (a.win_rate || 0);
    } else if (sortBy === 'compliance') {
      return b.template_compliance_pct - a.template_compliance_pct;
    }
    return b.volatility_adjusted_score - a.volatility_adjusted_score;
  });

  return (
    <div className="space-y-6 bg-linear-to-b from-[#0f1117] to-[#1a1d2e] min-h-screen p-6">
      <PageHeader title="War Room Leaderboard" />

      {/* Explanation */}
      <div className="bg-[#2a2e44]/50 border-l-4 border-cyan-500 p-4 rounded-lg">
        <h3 className="text-sm font-bold text-cyan-400 mb-2">How It Works</h3>
        <p className="text-xs text-gray-300">
          Leaderboard is <strong>risk-adjusted</strong>, not based on likes or hype. Ranked by volatility-adjusted
          score, which accounts for win rate, sample size, and drawdown. To get <strong>Verified</strong> status, you
          need 20+ graded picks (receipts) with 52%+ win rate.
        </p>
      </div>

      {/* Sort Controls */}
      <div className="flex gap-2 flex-wrap">
        {[
          { id: 'score', label: '📊 Volatility Score' },
          { id: 'win_rate', label: '📈 Win Rate' },
          { id: 'compliance', label: '✓ Template Compliance' },
        ].map((option) => (
          <button
            key={option.id}
            onClick={() => setSortBy(option.id as any)}
            className={`px-4 py-2 rounded-lg font-bold text-xs transition ${
              sortBy === option.id
                ? 'bg-cyan-500 text-gray-900'
                : 'bg-[#2a2e44] hover:bg-[#3a3e54] text-gray-300'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Leaderboard Table */}
      <div className="bg-[#1a1d2e] rounded-lg border border-[#2a2e44] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#2a2e44] border-b border-[#3a3e54]">
              <th className="px-4 py-3 text-left font-bold text-gray-300">#</th>
              <th className="px-4 py-3 text-left font-bold text-gray-300">Username</th>
              <th className="px-4 py-3 text-center font-bold text-gray-300">Rank</th>
              <th className="px-4 py-3 text-right font-bold text-gray-300">Vol Score</th>
              <th className="px-4 py-3 text-right font-bold text-gray-300">Win Rate</th>
              <th className="px-4 py-3 text-right font-bold text-gray-300">Picks</th>
              <th className="px-4 py-3 text-right font-bold text-gray-300">Compliance</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((entry, idx) => (
              <tr
                key={entry.user_id}
                className={`border-b border-[#2a2e44] hover:bg-[#2a2e44]/50 transition ${
                  idx < 3 ? 'bg-[#2a2e44]/30' : ''
                }`}
              >
                {/* Position */}
                <td className="px-4 py-3 font-bold text-white">
                  <span className="text-lg">{getMedalIcon(entry.leaderboard_position)}</span>
                </td>

                {/* Username */}
                <td className="px-4 py-3">
                  <div className="space-y-1">
                    <p className="font-bold text-gray-100">{entry.username}</p>
                    <div className="flex items-center gap-1 flex-wrap">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-bold ${getRankBgColor(
                          entry.rank
                        )}`}
                      >
                        {entry.rank.toUpperCase()}
                      </span>
                      {entry.has_verified_track_record && (
                        <span className="text-xs text-green-400 flex items-center gap-0.5">
                          <CheckCircle size={12} /> Verified Track
                        </span>
                      )}
                      {entry.badges.map((badge) => (
                        <span key={badge} className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">
                          {badge}
                        </span>
                      ))}
                    </div>
                  </div>
                </td>

                {/* Rank Badge */}
                <td className="px-4 py-3 text-center">
                  <div
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full bg-linear-to-br ${getRankColor(
                      entry.rank
                    )}`}
                  >
                    <span className="text-xs font-bold text-white">
                      {entry.rank === 'elite' && '⭐'}
                      {entry.rank === 'verified' && '✓'}
                      {entry.rank === 'contributor' && '→'}
                      {entry.rank === 'rookie' && 'R'}
                    </span>
                  </div>
                </td>

                {/* Vol Score */}
                <td className="px-4 py-3 text-right">
                  <p className="font-bold text-cyan-400">{entry.volatility_adjusted_score.toFixed(1)}</p>
                </td>

                {/* Win Rate */}
                <td className="px-4 py-3 text-right">
                  {entry.win_rate ? (
                    <div className="space-y-1">
                      <p className="font-bold text-gray-100">{(entry.win_rate * 100).toFixed(1)}%</p>
                      <div className="w-16 bg-[#2a2e44] rounded-full h-1 ml-auto">
                        <div
                          className={`h-full rounded-full ${
                            entry.win_rate > 0.55
                              ? 'bg-green-500'
                              : entry.win_rate > 0.50
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${entry.win_rate * 100}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-gray-400 text-xs">—</p>
                  )}
                </td>

                {/* Sample Size */}
                <td className="px-4 py-3 text-right">
                  <p className="font-bold text-gray-100">{entry.sample_size}</p>
                  <p className="text-xs text-gray-400">{entry.max_drawdown ? `DD: ${(entry.max_drawdown * 100).toFixed(1)}%` : ''}</p>
                </td>

                {/* Compliance */}
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <span className="font-bold text-gray-100">{entry.template_compliance_pct.toFixed(0)}%</span>
                    {entry.template_compliance_pct >= 95 && (
                      <CheckCircle size={14} className="text-green-400" />
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Notes */}
      <div className="bg-[#2a2e44]/30 border border-[#3a3e54] rounded-lg p-4 text-xs text-gray-300 space-y-2">
        <p>
          <strong>Volatility-Adjusted Score:</strong> Combines win rate, sample size, and drawdown to surface
          consistent, disciplined players.
        </p>
        <p>
          <strong>No Receipts?</strong> You can still post and participate, but you won't get <strong>Verified</strong>{' '}
          badge without graded picks.
        </p>
        <p>
          <strong>Transparent:</strong> All metrics are calculated from publicly-submitted data. No algorithmic
          manipulation.
        </p>
      </div>
    </div>
  );
};

export default WarRoomLeaderboard;
