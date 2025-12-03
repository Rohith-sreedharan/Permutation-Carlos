import React, { useState, useEffect } from 'react';
import { fetchEvents } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import type { Event as EventType } from '../types';

interface ParlayLeg {
  event_id: string;
  pick_type: string;  // "spread", "total", "moneyline"
  selection: string;  // e.g., "Miami -5", "Over 215.5"
  true_probability: number;  // Model probability (0-1 scale)
  american_odds: number;  // e.g., -110
  sport: string;  // e.g., "NBA"
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

interface ParlayCalculation {
  combined_probability: number;  // 0-1 scale
  combined_probability_pct: number;  // Percentage
  correlation_type: string;  // "positive" | "negative" | "neutral"
  correlation_label: string;  // Human-readable
  decimal_odds: number;
  ev_percent: number;
  ev_interpretation: string;  // "Positive" | "Neutral" | "Negative"
  ev_label: string;  // "Strong Edge" | "Medium Edge" | etc.
  volatility: string;  // "Low" | "Medium" | "High" | "Extreme"
  stake_amount?: number;
  potential_payout?: number;
  potential_profit?: number;
  leg_count: number;
}

interface StakeAnalysis {
  hit_probability: number;  // Percentage (e.g., 4.1)
  hit_probability_label: string;  // "Very Low" | "Low" | "Moderate" | "Good" | "High"
  risk_level: string;  // "Low ✅" | "Medium ⚡" | "High 🔥" | "Extreme 🚨"
  ev_interpretation: string;  // "Positive" | "Neutral" | "Negative"
  context_message: string;  // Main interpretation
  payout_context: string;  // Payout vs probability context
  volatility_alignment: string;  // Risk alignment interpretation
}

const ParlayBuilder: React.FC = () => {
  const [events, setEvents] = useState<EventType[]>([]);
  const [legs, setLegs] = useState<ParlayLeg[]>([]);
  const [parlayCalc, setParlayCalc] = useState<ParlayCalculation | null>(null);
  const [stakeAnalysis, setStakeAnalysis] = useState<StakeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'moneyline' | 'spreads' | 'totals'>('moneyline');
  const [stake, setStake] = useState(100);
  const [shareSuccess, setShareSuccess] = useState(false);

  // Auto-calculate when legs or stake changes
  useEffect(() => {
    if (legs.length >= 2) {
      calculateParlay();
    } else {
      setParlayCalc(null);
      setStakeAnalysis(null);
    }
  }, [legs, stake]);

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

    // Extract true probability from simulation data (if available)
    // In production, this would come from the event's simulation object
    // For now, use reasonable defaults based on pick type
    let trueProbability = 0.5;  // Default 50%
    
    // You can enhance this later to use actual simulation data
    // const simulation = (event as any).simulation;
    // if (simulation) { ... }

    // Standard odds for demonstration (in production, fetch from odds API)
    const americanOdds = -110;

    const newLeg: ParlayLeg = {
      event_id: eventId,
      pick_type: pickType,
      selection: selection,
      true_probability: trueProbability,
      american_odds: americanOdds,
      sport: event.sport_key || 'NBA',
      team_a: event.home_team,
      team_b: event.away_team
    };

    setLegs([...legs, newLeg]);
  };

  const removeLeg = (index: number) => {
    const newLegs = legs.filter((_, i) => i !== index);
    setLegs(newLegs);
  };

  const calculateParlay = async () => {
    if (legs.length < 2) return;

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('authToken');
      
      // Call NEW parlay calculator endpoint
      const response = await fetch('http://localhost:8000/api/architect/calculate-parlay', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          legs: legs,
          stake_amount: stake
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to calculate parlay');
      }

      const data: ParlayCalculation = await response.json();
      setParlayCalc(data);
      
      // Now calculate stake intelligence
      await analyzeStake(data);
    } catch (err: any) {
      setError(err.message || 'Failed to calculate parlay');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Share Button Handler
  const handleShare = async () => {
    if (!parlayCalc) return;

    const legsText = legs.map((leg, idx) => 
      `${idx + 1}. ${leg.team_a} vs ${leg.team_b} - ${leg.pick_type.toUpperCase()} ${leg.selection.toUpperCase()}`
    ).join('\n');

    const evText = parlayCalc.ev_percent > 0 ? `+${parlayCalc.ev_percent.toFixed(1)}%` : `${parlayCalc.ev_percent.toFixed(1)}%`;
    const correlationEmoji = parlayCalc.correlation_type === 'positive' ? '🟢' : 
                             parlayCalc.correlation_type === 'negative' ? '🔴' : '🟡';

    const shareText = `🚀 Just built a ${legs.length}-leg parlay on #BeatVegas!\n\n${legsText}\n\n${correlationEmoji} ${parlayCalc.correlation_label}\n💰 Expected Value: ${evText}\n🎲 Hit Probability: ${parlayCalc.combined_probability_pct.toFixed(1)}%\n\nCheck the AI model: beatvegas.com`;

    try {
      await navigator.clipboard.writeText(shareText);
      setShareSuccess(true);
      setTimeout(() => setShareSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      alert('Failed to copy. Please try again.');
    }
  };

  const analyzeStake = async (parlayData: ParlayCalculation) => {
    try {
      const token = localStorage.getItem('authToken');
      
      // Determine parlay confidence based on EV%
      let parlayConfidence = 'MODERATE';
      if (parlayData.ev_percent < -5) {
        parlayConfidence = 'SPECULATIVE';
      } else if (parlayData.ev_percent > 5) {
        parlayConfidence = 'HIGH';
      }
      
      const response = await fetch('http://localhost:8000/api/architect/analyze-stake', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          stake_amount: stake,
          parlay_confidence: parlayConfidence,
          parlay_risk: parlayData.volatility,
          leg_count: parlayData.leg_count,
          combined_probability: parlayData.combined_probability,
          total_odds: parlayData.decimal_odds,
          potential_payout: parlayData.potential_payout || (stake * parlayData.decimal_odds),
          ev_percent: parlayData.ev_percent
        }),
      });

      if (response.ok) {
        const stakeData = await response.json();
        setStakeAnalysis(stakeData);
      }
    } catch (err) {
      console.error('Failed to analyze stake:', err);
    }
  };

  // Traffic Light Colors for Correlation
  const getCorrelationColor = (type: string) => {
    switch (type) {
      case 'positive': return { bg: 'bg-green-500/20', border: 'border-green-500', text: 'text-green-500', icon: '🟢' };
      case 'negative': return { bg: 'bg-red-500/20', border: 'border-red-500', text: 'text-red-500', icon: '🔴' };
      case 'neutral': return { bg: 'bg-yellow-500/20', border: 'border-yellow-500', text: 'text-yellow-500', icon: '🟡' };
      default: return { bg: 'bg-gray-500/20', border: 'border-gray-500', text: 'text-gray-500', icon: '⚪' };
    }
  };

  // Color-coded hit probability (requirement #5)
  const getProbabilityColor = (prob: number) => {
    if (prob < 5) return 'text-red-400';      // 0-5%: red
    if (prob < 15) return 'text-yellow-400';  // 5-15%: yellow
    if (prob < 25) return 'text-lime-400';    // 15-25%: greenish
    return 'text-green-400';                   // 25%+: green
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
                          {leg.pick_type.toUpperCase()} - {leg.selection.toUpperCase()} ({(leg.true_probability * 100).toFixed(1)}%)
                        </div>
                      </div>
                      <button
                        onClick={() => removeLeg(idx)}
                        className="text-bold-red hover:text-white text-xl"
                      >
                        ×
                      </button>
                    </div>
                    {/* Visual Link Indicator for positive correlation */}
                    {idx < legs.length - 1 && parlayCalc && parlayCalc.correlation_type === 'positive' && (
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
                  onChange={(e) => {
                    setStake(parseFloat(e.target.value));
                    setStakeAnalysis(null); // Clear previous analysis when stake changes
                  }}
                  className="w-full bg-navy border border-navy rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-electric-blue focus:outline-none"
                />
              </div>
            )}

            {/* Analyze Button - Hidden (auto-calculates) */}
            <button
              onClick={calculateParlay}
              disabled={legs.length < 2 || loading}
              className="w-full bg-gradient-to-r from-electric-blue to-purple-600 text-white font-bold py-3 px-6 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all"
            >
              {loading ? 'Calculating...' : legs.length < 2 ? 'Add 2+ Legs to Analyze' : 'Recalculate Parlay'}
            </button>

            {/* Error Message */}
            {error && (
              <div className="mt-4 bg-bold-red/20 border border-bold-red rounded-lg p-3 text-bold-red text-sm">
                {error}
              </div>
            )}

            {/* Analysis Results */}
            {parlayCalc && (
              <div className="mt-6 space-y-4">
                {/* 🧠 STAKE INTELLIGENCE (CONTEXT ONLY) */}
                {stakeAnalysis && (
                  <div className="bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-xl p-5 border-2 border-purple-500/30">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h4 className="text-white font-bold text-base mb-1 flex items-center gap-2">
                          🧠 Stake Intelligence
                        </h4>
                        <p className="text-light-gray text-xs mb-3">
                          Context only — not betting advice
                        </p>
                      </div>
                    </div>
                    
                    {/* Key Metrics Grid */}
                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="bg-navy/50 rounded-lg p-3">
                        <div className="text-light-gray text-xs mb-1">Hit Probability</div>
                        <div className={`text-xl font-bold ${
                          stakeAnalysis.hit_probability < 10 ? 'text-red-400' :
                          stakeAnalysis.hit_probability < 20 ? 'text-yellow-400' :
                          'text-green-400'
                        }`}>
                          {stakeAnalysis.hit_probability.toFixed(1)}%
                        </div>
                        <div className="text-xs text-light-gray">{stakeAnalysis.hit_probability_label}</div>
                      </div>
                      
                      <div className="bg-navy/50 rounded-lg p-3">
                        <div className="text-light-gray text-xs mb-1">Risk Level</div>
                        <div className="text-lg font-bold text-white">
                          {stakeAnalysis.risk_level}
                        </div>
                      </div>
                      
                      <div className="bg-navy/50 rounded-lg p-3">
                        <div className="text-light-gray text-xs mb-1">EV</div>
                        <div className={`text-lg font-bold ${
                          stakeAnalysis.ev_interpretation === 'Positive' ? 'text-green-400' :
                          stakeAnalysis.ev_interpretation === 'Negative' ? 'text-red-400' :
                          'text-yellow-400'
                        }`}>
                          {stakeAnalysis.ev_interpretation}
                        </div>
                      </div>
                    </div>
                    
                    {/* Context Messages */}
                    <div className="space-y-2">
                      <div className="bg-navy/30 rounded-lg p-3">
                        <div className="text-xs text-light-gray mb-1">Context:</div>
                        <div className="text-sm text-white">{stakeAnalysis.context_message}</div>
                      </div>
                      
                      <div className="text-xs text-light-gray">
                        {stakeAnalysis.payout_context}
                      </div>
                      
                      <div className="text-xs text-light-gray italic">
                        {stakeAnalysis.volatility_alignment}
                      </div>
                    </div>
                  </div>
                )}

                {/* 📊 PARLAY METRICS (Real Calculator Data) */}
                <div className="bg-gradient-to-br from-navy to-charcoal rounded-xl p-6 border-2 border-gold/30">
                  <h3 className="text-gold font-bold text-lg mb-4 flex items-center gap-2">
                    📊 Parlay Analysis
                  </h3>
                  
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    {/* Hit Probability - COLOR CODED */}
                    <div className="bg-navy/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-1">Win Probability</div>
                      <div className={`font-bold text-2xl ${getProbabilityColor(parlayCalc.combined_probability_pct)}`}>
                        {parlayCalc.combined_probability_pct.toFixed(1)}%
                      </div>
                      <div className="text-xs text-light-gray mt-1">
                        ({parlayCalc.leg_count} legs)
                      </div>
                    </div>
                    
                    {/* Decimal Odds */}
                    <div className="bg-navy/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-1">Payout Odds</div>
                      <div className="text-white font-bold text-2xl">
                        {parlayCalc.decimal_odds.toFixed(2)}x
                      </div>
                      <div className="text-xs text-light-gray mt-1">
                        {parlayCalc.potential_payout && `$${parlayCalc.potential_payout.toFixed(2)}`}
                      </div>
                    </div>
                    
                    {/* Expected Value */}
                    <div className="bg-navy/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-1">Expected Value</div>
                      <div className={`font-bold text-xl ${getEVColor(parlayCalc.ev_percent)}`}>
                        {parlayCalc.ev_percent > 0 ? '+' : ''}{parlayCalc.ev_percent.toFixed(1)}%
                      </div>
                      <div className="text-xs text-light-gray mt-1">
                        {parlayCalc.ev_label}
                      </div>
                    </div>
                    
                    {/* Volatility */}
                    <div className="bg-navy/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-1">Volatility</div>
                      <div className={`font-bold text-xl ${
                        parlayCalc.volatility === 'Extreme' ? 'text-red-400' :
                        parlayCalc.volatility === 'High' ? 'text-orange-400' :
                        parlayCalc.volatility === 'Medium' ? 'text-yellow-400' :
                        'text-green-400'
                      }`}>
                        {parlayCalc.volatility}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Correlation Badge */}
                <div className={`${getCorrelationColor(parlayCalc.correlation_type).bg} border-2 ${getCorrelationColor(parlayCalc.correlation_type).border} rounded-xl p-6 text-center`}>
                  <div className="text-5xl mb-2">{getCorrelationColor(parlayCalc.correlation_type).icon}</div>
                  <div className={`text-2xl font-bold font-teko ${getCorrelationColor(parlayCalc.correlation_type).text}`}>
                    {parlayCalc.correlation_label.toUpperCase()}
                  </div>
                  <div className="text-light-gray text-sm mt-2">
                    {parlayCalc.correlation_type === 'positive' && 'Legs tend to hit together'}
                    {parlayCalc.correlation_type === 'negative' && 'Legs work against each other'}
                    {parlayCalc.correlation_type === 'neutral' && 'No significant correlation detected'}
                  </div>
                </div>

                {/* Potential Profit Display */}
                {parlayCalc.potential_profit && (
                  <div className="bg-gradient-to-r from-neon-green/20 to-emerald-500/20 border-2 border-neon-green/50 rounded-xl p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-light-gray text-sm">Potential Profit</div>
                        <div className="text-neon-green font-bold text-3xl font-teko">
                          ${parlayCalc.potential_profit.toFixed(2)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-light-gray text-sm">Total Payout</div>
                        <div className="text-white font-bold text-xl">
                          ${parlayCalc.potential_payout?.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* EV WARNING for negative EV parlays */}
                {parlayCalc.ev_percent < -10 && (
                  <div className="bg-gradient-to-r from-red-900/30 to-red-800/20 border-4 border-red-500 rounded-2xl p-6">
                    <div className="flex items-center space-x-4 mb-3">
                      <div className="text-5xl">⚠️</div>
                      <div>
                        <div className="text-red-400 font-black text-xl">NEGATIVE EV WARNING</div>
                        <div className="text-white font-semibold">This parlay is mathematically disadvantageous</div>
                      </div>
                    </div>
                    <div className="bg-black/40 rounded-lg p-4 border border-red-500/50">
                      <p className="text-light-gray text-sm">
                        <span className="font-semibold text-white">EV: {parlayCalc.ev_percent.toFixed(1)}%</span> — 
                        The payout odds don't fairly compensate for the low hit probability. 
                        {parlayCalc.correlation_type === 'negative' && (
                          <span className="text-red-400 block mt-2">
                            🚨 Legs correlate negatively, making this even less likely to hit.
                          </span>
                        )}
                      </p>
                    </div>
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
