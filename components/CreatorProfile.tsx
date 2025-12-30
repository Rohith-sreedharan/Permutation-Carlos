import React, { useState, useEffect } from 'react';
import { apiRequest } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';

interface CreatorStats {
  username: string;
  avatar_url?: string;
  roi: number;
  win_rate: number;
  total_bets: number;
  total_units_won: number;
  sharpe_ratio: number;
  avg_odds: number;
  badges: string[];
}

interface RecentSlip {
  slip_id: string;
  sport: string;
  pick_type: string;
  selection: string;
  odds: number;
  stake: number;
  outcome?: 'win' | 'loss' | 'pending';
  settled_at?: string;
  profit?: number;
}

interface CreatorProfileProps {
  username: string;
  onTailParlay: (slipId: string) => void;
  onBack: () => void;
}

const CreatorProfile: React.FC<CreatorProfileProps> = ({ username, onTailParlay, onBack }) => {
  const [stats, setStats] = useState<CreatorStats | null>(null);
  const [recentSlips, setRecentSlips] = useState<RecentSlip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedSlipId, setCopiedSlipId] = useState<string | null>(null);

  useEffect(() => {
    loadCreatorData();
  }, [username]);

  const loadCreatorData = async () => {
    try {
      setLoading(true);
      const [statsData, slipsData] = await Promise.all([
        apiRequest<CreatorStats>(`/api/creator/${username}/stats`),
        apiRequest<RecentSlip[]>(`/api/creator/${username}/slips?limit=10`)
      ]);

      setStats(statsData);
      setRecentSlips(slipsData);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load creator profile');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTailThis = (slipId: string) => {
    onTailParlay(slipId);
    setCopiedSlipId(slipId);
    setTimeout(() => setCopiedSlipId(null), 2000);
  };

  const getBadgeIcon = (badge: string): string => {
    const badgeMap: Record<string, string> = {
      'certified_sharp': '🏆',
      'volume_king': '👑',
      'hot_streak': '🔥',
      'diamond_hands': '💎',
      'underdog_killer': '🐕',
      'parlay_master': '🎯'
    };
    return badgeMap[badge] || '⭐';
  };

  const getBadgeLabel = (badge: string): string => {
    const labels: Record<string, string> = {
      'certified_sharp': 'Certified Sharp',
      'volume_king': 'Volume King',
      'hot_streak': 'Hot Streak',
      'diamond_hands': 'Diamond Hands',
      'underdog_killer': 'Underdog Killer',
      'parlay_master': 'Parlay Master'
    };
    return labels[badge] || badge;
  };

  const getBadgeDescription = (badge: string): string => {
    const descriptions: Record<string, string> = {
      'certified_sharp': 'ROI > 10% over 50+ bets',
      'volume_king': '100+ bets this month',
      'hot_streak': '5+ wins in a row',
      'diamond_hands': 'Held winning positions through volatility',
      'underdog_killer': '60%+ win rate on underdogs',
      'parlay_master': 'Exceptional multi-leg success'
    };
    return descriptions[badge] || 'Verified achievement';
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-center text-bold-red p-8">{error}</div>;
  if (!stats) return <div className="text-center text-light-gray p-8">Creator not found</div>;

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      {/* Back Button */}
      <button
        onClick={onBack}
        className="text-electric-blue hover:text-white mb-4 flex items-center space-x-2 transition"
      >
        <span>←</span>
        <span>Back to Leaderboard</span>
      </button>

      {/* Creator Header */}
      <div className="bg-linear-to-r from-purple-900/30 to-pink-900/30 border-2 border-purple-500/30 rounded-xl p-8 mb-6">
        <div className="flex items-center space-x-6">
          {/* Avatar */}
          <div className="w-24 h-24 rounded-full bg-linear-to-br from-purple-500 to-pink-500 flex items-center justify-center text-4xl font-bold text-white">
            {stats.avatar_url ? (
              <img src={stats.avatar_url} alt={stats.username} className="w-full h-full rounded-full" />
            ) : (
              stats.username.charAt(0).toUpperCase()
            )}
          </div>

          {/* Username & Badges */}
          <div className="flex-1">
            <h1 className="text-4xl font-bold text-white font-teko mb-2">@{stats.username}</h1>
            
            {/* Verified Badges */}
            {stats.badges.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {stats.badges.map((badge) => (
                  <div
                    key={badge}
                    className="bg-linear-to-r from-yellow-600 to-orange-600 text-white text-xs font-bold px-3 py-1 rounded-full flex items-center space-x-1"
                    title={getBadgeDescription(badge)}
                  >
                    <span>{getBadgeIcon(badge)}</span>
                    <span>{getBadgeLabel(badge)}</span>
                  </div>
                ))}
              </div>
            )}

            <p className="text-light-gray">
              Influencer • {stats.total_bets} total bets • {stats.total_units_won > 0 ? '+' : ''}{stats.total_units_won.toFixed(1)} units
            </p>
          </div>

          {/* ROI Highlight */}
          <div className="text-right">
            <div className="text-sm text-light-gray mb-1">Return on Investment</div>
            <div className={`text-5xl font-bold ${stats.roi > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
              {stats.roi > 0 ? '+' : ''}{stats.roi.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <div className="text-light-gray text-sm mb-2">Win Rate</div>
          <div className="text-3xl font-bold text-white">{stats.win_rate.toFixed(1)}%</div>
        </div>
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <div className="text-light-gray text-sm mb-2">Total Bets</div>
          <div className="text-3xl font-bold text-white">{stats.total_bets}</div>
        </div>
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <div className="text-light-gray text-sm mb-2">Sharpe Ratio</div>
          <div className="text-3xl font-bold text-white">{stats.sharpe_ratio.toFixed(2)}</div>
        </div>
        <div className="bg-charcoal rounded-xl p-6 border border-navy">
          <div className="text-light-gray text-sm mb-2">Avg Odds</div>
          <div className="text-3xl font-bold text-white">{stats.avg_odds > 0 ? '+' : ''}{stats.avg_odds.toFixed(0)}</div>
        </div>
      </div>

      {/* Recent Slips */}
      <PageHeader title="Recent Picks">
        <span className="text-sm text-light-gray">Last 10 settled bets</span>
      </PageHeader>

      <div className="space-y-3">
        {recentSlips.map((slip) => (
          <div
            key={slip.slip_id}
            className="bg-charcoal rounded-lg p-4 border border-navy hover:border-electric-blue transition-all"
          >
            <div className="flex items-center justify-between">
              {/* Slip Details */}
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-2 py-1 rounded uppercase">
                    {slip.sport}
                  </span>
                  <span className="text-white font-semibold">{slip.pick_type}</span>
                  {slip.outcome && (
                    <span
                      className={`text-xs font-bold px-2 py-1 rounded ${
                        slip.outcome === 'win'
                          ? 'bg-neon-green/20 text-neon-green'
                          : slip.outcome === 'loss'
                          ? 'bg-bold-red/20 text-bold-red'
                          : 'bg-yellow-500/20 text-yellow-500'
                      }`}
                    >
                      {slip.outcome.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="text-light-gray text-sm">
                  {slip.selection} @ {slip.odds > 0 ? '+' : ''}{slip.odds}
                </div>
                {slip.profit !== undefined && (
                  <div className={`text-sm font-semibold mt-1 ${slip.profit > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                    {slip.profit > 0 ? '+' : ''}{slip.profit.toFixed(2)} units
                  </div>
                )}
              </div>

              {/* Tail This Button */}
              <button
                onClick={() => handleTailThis(slip.slip_id)}
                className="bg-linear-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-bold px-6 py-3 rounded-lg transition-all transform hover:scale-105 flex items-center space-x-2"
              >
                <span>📋</span>
                <span>{copiedSlipId === slip.slip_id ? 'Copied!' : 'Tail This'}</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {recentSlips.length === 0 && (
        <div className="text-center text-light-gray p-8">
          No recent bets available
        </div>
      )}
    </div>
  );
};

export default CreatorProfile;
