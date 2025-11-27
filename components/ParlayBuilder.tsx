import React, { useState, useEffect } from 'react';
import { fetchEvents } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import type { Event as EventType } from '../types';

interface ParlayLeg {
  event_id: string;
  pick_type: string;
  selection: string;
  odds: number;
  win_probability: number;
  team_a?: string;
  team_b?: string;
  line?: number;
  player?: string;
}

interface ParlayAnalysisResponse {
  request_id: string;
  correlation_grade: string;
  correlation_score: number;
  combined_true_probability: number;
  implied_book_probability: number;
  naive_probability: number;
  EV_WARNING: boolean;
  ev_percent: number;
  analysis: string;
  recommended_stake: number;
  same_game_parlay: boolean;
}

const ParlayBuilder: React.FC = () => {
  const [events, setEvents] = useState<EventType[]>([]);
  const [legs, setLegs] = useState<ParlayLeg[]>([]);
  const [analysis, setAnalysis] = useState<ParlayAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'moneyline' | 'spreads' | 'totals'>('moneyline');
  const [stake, setStake] = useState(100);
  const [shareSuccess, setShareSuccess] = useState(false);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    try {
      setEventsLoading(true);
      const data = await fetchEvents();
      setEvents(data.slice(0, 10)); // Show first 10 events
    } catch (err) {
      console.error('Failed to load events:', err);
    } finally {
      setEventsLoading(false);
    }
  };

  const addLeg = (eventId: string, pickType: string, selection: string) => {
    const event = events.find(e => e.id === eventId);
    if (!event) return;

    // Simulate odds and probabilities (in production, fetch from API)
    const odds = 1.85 + Math.random() * 0.3;
    const winProb = 0.50 + Math.random() * 0.2;

    const newLeg: ParlayLeg = {
      event_id: eventId,
      pick_type: pickType,
      selection: selection,
      odds: parseFloat(odds.toFixed(2)),
      win_probability: parseFloat(winProb.toFixed(2)),
      team_a: event.home_team,
      team_b: event.away_team
    };

    setLegs([...legs, newLeg]);
    setAnalysis(null); // Clear previous analysis
  };

  const removeLeg = (index: number) => {
    const newLegs = legs.filter((_, i) => i !== index);
    setLegs(newLegs);
    setAnalysis(null);
  };

  // Share Button Handler (Blueprint Page 64: Creator Distribution Moat)
  const handleShare = async () => {
    if (!analysis) return;

    const legsText = legs.map((leg, idx) => 
      `${idx + 1}. ${leg.team_a} vs ${leg.team_b} - ${leg.pick_type.toUpperCase()} ${leg.selection.toUpperCase()}`
    ).join('\n');

    const evText = analysis.ev_percent > 0 ? `+${analysis.ev_percent.toFixed(1)}%` : `${analysis.ev_percent.toFixed(1)}%`;
    const correlationEmoji = analysis.correlation_grade === 'HIGH' ? '🔴' : 
                             analysis.correlation_grade === 'MEDIUM' ? '🟡' : '🟢';

    const shareText = `🚀 Just built a ${legs.length}-leg parlay on #BeatVegas!\n\n${legsText}\n\n${correlationEmoji} Correlation: ${analysis.correlation_grade}\n💰 Expected Value: ${evText}\n🎯 Kelly Stake: $${analysis.recommended_stake.toFixed(0)}\n\nCheck the AI model: beatvegas.com`;

    try {
      await navigator.clipboard.writeText(shareText);
      setShareSuccess(true);
      setTimeout(() => setShareSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      alert('Failed to copy. Please try again.');
    }
  };

  const analyzeParlay = async () => {
    if (legs.length < 2) {
      setError('Add at least 2 legs to analyze correlation');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:8000/api/parlay/build', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ legs, stake }),
      });

      if (!response.ok) {
        throw new Error('Failed to analyze parlay');
      }

      const data = await response.json();
      setAnalysis(data);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze parlay');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Traffic Light Colors - PHASE 7: Added CROSS_SPORT grade
  const getCorrelationColor = (grade: string) => {
    switch (grade) {
      case 'HIGH': return { bg: 'bg-bold-red/20', border: 'border-bold-red', text: 'text-bold-red', icon: '🔴' };
      case 'MEDIUM': return { bg: 'bg-yellow-500/20', border: 'border-yellow-500', text: 'text-yellow-500', icon: '🟡' };
      case 'LOW': return { bg: 'bg-neon-green/20', border: 'border-neon-green', text: 'text-neon-green', icon: '🟢' };
      case 'CROSS_SPORT': return { bg: 'bg-blue-500/20', border: 'border-blue-500', text: 'text-blue-500', icon: '🔵' };
      case 'NEGATIVE': return { bg: 'bg-purple-600/20', border: 'border-purple-600', text: 'text-purple-600', icon: '🟣' };
      default: return { bg: 'bg-light-gray/20', border: 'border-light-gray', text: 'text-light-gray', icon: '⚪' };
    }
  };

  const getEVColor = (ev: number) => {
    if (ev > 10) return 'text-neon-green';
    if (ev > 0) return 'text-electric-blue';
    return 'text-bold-red';
  };

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <PageHeader title="🎯 Interactive Parlay Builder">
        <div className="flex items-center space-x-2">
          <span className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-3 py-1 rounded-full">
            CORRELATION ANALYSIS
          </span>
        </div>
      </PageHeader>

      {/* Split Screen Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT PANEL: Game/Prop Selector */}
        <div className="space-y-4">
          <div className="bg-charcoal rounded-xl p-6 border border-navy">
            <h3 className="text-xl font-bold text-white font-teko mb-4">SELECT PICKS</h3>

            {/* Tabs */}
            <div className="flex space-x-2 mb-4 border-b border-navy pb-3">
              <button
                onClick={() => setActiveTab('moneyline')}
                className={`px-4 py-2 rounded-t-lg font-semibold text-sm transition ${
                  activeTab === 'moneyline'
                    ? 'bg-electric-blue text-white'
                    : 'bg-charcoal text-light-gray hover:text-white'
                }`}
              >
                Moneyline
              </button>
              <button
                onClick={() => setActiveTab('spreads')}
                className={`px-4 py-2 rounded-t-lg font-semibold text-sm transition ${
                  activeTab === 'spreads'
                    ? 'bg-electric-blue text-white'
                    : 'bg-charcoal text-light-gray hover:text-white'
                }`}
              >
                Spreads
              </button>
              <button
                onClick={() => setActiveTab('totals')}
                className={`px-4 py-2 rounded-t-lg font-semibold text-sm transition ${
                  activeTab === 'totals'
                    ? 'bg-electric-blue text-white'
                    : 'bg-charcoal text-light-gray hover:text-white'
                }`}
              >
                Totals
              </button>
            </div>

            {/* Event List */}
            {eventsLoading ? (
              <LoadingSpinner />
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {events.map(event => (
                  <div key={event.id} className="bg-navy/30 rounded-lg p-4 border border-navy hover:border-electric-blue transition">
                    <div className="text-white font-semibold mb-2">
                      {event.away_team} @ {event.home_team}
                    </div>
                    <div className="text-xs text-light-gray mb-3">
                      {new Date(event.commence_time).toLocaleString()}
                    </div>
                    
                    {activeTab === 'moneyline' && (
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => addLeg(event.id, 'moneyline', 'home')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          {event.home_team} ML
                        </button>
                        <button
                          onClick={() => addLeg(event.id, 'moneyline', 'away')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          {event.away_team} ML
                        </button>
                      </div>
                    )}

                    {activeTab === 'spreads' && (
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => addLeg(event.id, 'spread', 'home')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          {event.home_team} -6.5
                        </button>
                        <button
                          onClick={() => addLeg(event.id, 'spread', 'away')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          {event.away_team} +6.5
                        </button>
                      </div>
                    )}

                    {activeTab === 'totals' && (
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => addLeg(event.id, 'total', 'over')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          Over 215.5
                        </button>
                        <button
                          onClick={() => addLeg(event.id, 'total', 'under')}
                          className="bg-charcoal hover:bg-electric-blue text-white px-3 py-2 rounded text-sm transition"
                        >
                          Under 215.5
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANEL: Slip Analysis */}
        <div className="space-y-4">
          <div className="bg-charcoal rounded-xl p-6 border border-navy sticky top-6">
            <h3 className="text-xl font-bold text-white font-teko mb-4">SLIP ANALYSIS</h3>

            {/* Current Legs */}
            <div className="space-y-2 mb-4 max-h-[250px] overflow-y-auto">
              {legs.length === 0 ? (
                <div className="text-center text-light-gray py-8">
                  <div className="text-4xl mb-2">🎯</div>
                  <div>Add picks from the left to build your parlay</div>
                </div>
              ) : (
                legs.map((leg, idx) => (
                  <div key={idx} className="relative">
                    <div className="bg-navy/30 rounded-lg p-3 flex items-center justify-between">
                      <div className="flex-1">
                        <div className="text-white font-semibold text-sm">
                          {leg.team_a} vs {leg.team_b}
                        </div>
                        <div className="text-xs text-light-gray">
                          {leg.pick_type.toUpperCase()} - {leg.selection.toUpperCase()} @ {leg.odds.toFixed(2)}
                        </div>
                      </div>
                      <button
                        onClick={() => removeLeg(idx)}
                        className="text-bold-red hover:text-white text-xl"
                      >
                        ×
                      </button>
                    </div>
                    {/* Visual Link Indicator for HIGH correlation (Blueprint Page 64) */}
                    {idx < legs.length - 1 && analysis && analysis.correlation_grade === 'HIGH' && (
                      <div className="flex items-center justify-center my-1">
                        <div className="text-neon-green text-2xl animate-pulse" title="High correlation detected">
                          🔗
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Stake Input */}
            {legs.length > 0 && (
              <div className="mb-4">
                <label className="block text-light-gray text-sm mb-2">Stake Amount ($)</label>
                <input
                  type="number"
                  value={stake}
                  onChange={(e) => setStake(parseFloat(e.target.value))}
                  className="w-full bg-navy border border-navy rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
                />
              </div>
            )}

            {/* Analyze Button */}
            <button
              onClick={analyzeParlay}
              disabled={legs.length < 2 || loading}
              className="w-full bg-gradient-to-r from-electric-blue to-purple-600 text-white font-bold py-3 px-6 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
            >
              {loading ? 'Analyzing...' : legs.length < 2 ? 'Add 2+ Legs to Analyze' : 'Analyze Correlation'}
            </button>

            {/* Error Message */}
            {error && (
              <div className="mt-4 bg-bold-red/20 border border-bold-red rounded-lg p-3 text-bold-red text-sm">
                {error}
              </div>
            )}

            {/* Analysis Results */}
            {analysis && (
              <div className="mt-6 space-y-4">
                {/* Traffic Light Correlation Grade */}
                <div className={`${getCorrelationColor(analysis.correlation_grade).bg} border-2 ${getCorrelationColor(analysis.correlation_grade).border} rounded-xl p-6 text-center`}>
                  <div className="text-6xl mb-2">{getCorrelationColor(analysis.correlation_grade).icon}</div>
                  <div className={`text-3xl font-bold font-teko ${getCorrelationColor(analysis.correlation_grade).text}`}>
                    {analysis.correlation_grade} CORRELATION
                  </div>
                  <div className="text-white mt-2">{analysis.correlation_score.toFixed(2)}</div>
                </div>

                {/* Analysis Text */}
                <div className="bg-navy/50 rounded-lg p-4">
                  <p className="text-light-gray text-sm">{analysis.analysis}</p>
                </div>

                {/* Key Metrics */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-navy/50 rounded-lg p-4">
                    <div className="text-light-gray text-xs uppercase mb-1">True Probability</div>
                    <div className="text-white font-bold text-xl">
                      {(analysis.combined_true_probability * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 rounded-lg p-4">
                    <div className="text-light-gray text-xs uppercase mb-1">Book Probability</div>
                    <div className="text-white font-bold text-xl">
                      {(analysis.implied_book_probability * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 rounded-lg p-4">
                    <div className="text-light-gray text-xs uppercase mb-1">Expected Value</div>
                    <div className={`font-bold text-xl ${getEVColor(analysis.ev_percent)}`}>
                      {analysis.ev_percent > 0 ? '+' : ''}{analysis.ev_percent.toFixed(2)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 rounded-lg p-4">
                    <div className="text-light-gray text-xs uppercase mb-1">Kelly Stake</div>
                    <div className="text-neon-green font-bold text-xl">
                      ${analysis.recommended_stake.toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* LARGE RED EV WARNING BOX (Blueprint Page 64 requirement) */}
                {analysis.EV_WARNING && (
                  <div className="bg-gradient-to-r from-bold-red/30 to-bold-red/20 border-4 border-bold-red rounded-2xl p-6 shadow-2xl">
                    <div className="flex items-center space-x-4 mb-4">
                      <div className="text-6xl animate-pulse">⚠️</div>
                      <div className="flex-1">
                        <div className="text-bold-red font-black text-2xl mb-2 tracking-wide">NEGATIVE EV WARNING</div>
                        <div className="text-white font-bold text-lg">These picks fight each other statistically</div>
                      </div>
                    </div>
                    <div className="bg-black/40 rounded-lg p-4 border border-bold-red/50">
                      <p className="text-light-gray text-sm leading-relaxed">
                        <span className="font-semibold text-white">High correlation detected:</span> When one leg hits, it makes the other(s) less likely to win. 
                        The book's odds don't account for this dependency, creating negative expected value. 
                        <span className="text-bold-red font-bold block mt-2">💡 Recommendation: Split into separate straight bets.</span>
                      </p>
                    </div>
                  </div>
                )}

                {/* Same-Game Parlay Badge */}
                {analysis.same_game_parlay && (
                  <div className="bg-electric-blue/20 border border-electric-blue rounded-lg p-3 text-center">
                    <span className="text-electric-blue font-bold text-sm">📊 SAME-GAME PARLAY DETECTED</span>
                  </div>
                )}

                {/* SHARE BUTTON - Creator Distribution Moat (Blueprint Page 64) */}
                <button
                  onClick={handleShare}
                  className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white font-bold py-4 px-6 rounded-xl hover:shadow-2xl transition-all transform hover:scale-105 flex items-center justify-center space-x-3"
                >
                  <span className="text-2xl">📤</span>
                  <span className="text-lg">SHARE PARLAY</span>
                  {shareSuccess && <span className="text-neon-green ml-2">✓ Copied!</span>}
                </button>
                {shareSuccess && (
                  <div className="bg-neon-green/20 border border-neon-green rounded-lg p-3 text-center text-neon-green text-sm animate-pulse">
                    ✓ Parlay copied to clipboard! Share on social media with #BeatVegas
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParlayBuilder;
