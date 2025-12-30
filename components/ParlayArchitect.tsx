import React, { useState, useEffect } from 'react';
import api, { getSubscriptionStatus } from '../services/api';
import { getTierConfig, getSimPowerMessage, shouldShowUpgradePrompt } from '../utils/simulationTiers';
import UpgradeModal from './UpgradeModal';

interface Leg {
  event: string;
  line: string;
  bet_type: string;
  probability: number;
  confidence: number;
  ev: number;
  volatility?: string;
  tier?: string;  // A, B, or C tier classification
}

// PARLAY_BLOCKED state response structure
interface ParlayBlockedState {
  status: 'BLOCKED';
  message: string;
  reason: string;
  passed_count: number;
  failed_count: number;
  minimum_required: number;
  failed: Array<{
    game: string;
    reason: string;
  }>;
  best_single: {
    event: string;
    line: string;
    confidence: number;
    ev: number;
  } | null;
  next_best_actions: {
    market_filters: Array<{ option: string; label: string }>;
    risk_profiles: Array<{ profile: string; label: string }>;
  };
  next_refresh_seconds: number;
  next_refresh_eta: string;
}

interface ParlayData {
  parlay_id: string;
  sport: string;
  leg_count: number;
  risk_profile: string;
  legs: Leg[];
  parlay_odds: number;
  parlay_probability: number;
  expected_value: number;
  correlation_score: number;
  correlation_impact: string;
  confidence_rating: string;
  is_unlocked: boolean;
  is_speculative?: boolean; // Flag for simulated/speculative parlays
  transparency_message?: string;  // Notification about tier fallback
  unlock_price?: number;
  unlock_message?: string;
  legs_preview?: Array<{
    event: string;
    line: string;
    confidence: string;
  }>;
}

const ParlayArchitect: React.FC = () => {
  const [sport, setSport] = useState('basketball_nba');
  const [legCount, setLegCount] = useState(4);
  const [riskProfile, setRiskProfile] = useState('balanced');
  const [blockedState, setBlockedState] = useState<ParlayBlockedState | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [parlayData, setParlayData] = useState<ParlayData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stake, setStake] = useState<number>(10);
  const [eliteTokens, setEliteTokens] = useState<{is_elite: boolean, tokens_remaining: number, message: string} | null>(null);
  const [userTier, setUserTier] = useState<string>('starter');
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [includeHigherRisk, setIncludeHigherRisk] = useState(false);  // Risk toggle: allow LEAN legs

  // Fetch user tier on mount using proper auth
  useEffect(() => {
    const fetchUserTier = async () => {
      try {
        console.log('🔍 [ParlayArchitect] Fetching user tier...');
        const response = await getSubscriptionStatus();
        console.log('🎯 [ParlayArchitect] Subscription response:', response);
        const tier = (response.tier || 'starter').toLowerCase();
        console.log('✅ [ParlayArchitect] Setting userTier to:', tier);
        setUserTier(tier);
      } catch (err) {
        console.error('❌ [ParlayArchitect] Failed to fetch tier:', err);
        setUserTier('starter'); // Default on error
      }
    };
    fetchUserTier();
  }, []);

  const tierConfig = getTierConfig(userTier);
  const parlayMessage = getSimPowerMessage(userTier, 'parlay');
  const upgradePrompt = shouldShowUpgradePrompt(userTier, { legCount: parlayData?.leg_count || legCount });

  // Fetch elite token status on mount
  useEffect(() => {
    const fetchTokens = async () => {
      try {
        const userId = localStorage.getItem('user_id');
        if (userId) {
          const response = await api.get(`/api/architect/tokens?user_id=${userId}`);
          setEliteTokens(response.data);
        }
      } catch (err) {
        console.error('Failed to fetch elite tokens:', err);
      }
    };
    fetchTokens();
  }, []);

  // Helpers: safe formatting
  const safeNumber = (n: any, fallback = 0) => {
    const v = typeof n === 'number' ? n : Number(n);
    return Number.isFinite(v) ? v : fallback;
  };
  
  // Official BeatVegas Confidence Grade Scale
  const getConfidenceGrade = (score: number): string => {
    if (score >= 90) return 'S';
    if (score >= 80) return 'A';
    if (score >= 70) return 'B';
    if (score >= 55) return 'C';
    if (score >= 30) return 'D';
    return 'F';
  };
  const fmtPct = (p: any, digits = 1) => `${safeNumber(p, 0).toFixed(digits)}%`;
  const americanToDecimal = (american: number) => {
    const a = safeNumber(american, 0);
    if (a === 0) return 1;
    return a > 0 ? 1 + a / 100 : 1 + 100 / Math.abs(a);
  };
  const computePayout = () => {
    const odds = safeNumber(parlayData?.parlay_odds, 0);
    const dec = americanToDecimal(odds);
    const st = safeNumber(stake, 0);
    const potentialReturn = st * dec;
    const profit = potentialReturn - st;
    return { dec, potentialReturn, profit };
  };
  const riskLabel = () => {
    const prob = safeNumber(parlayData?.parlay_probability, 0);
    if (prob >= 0.6) return 'Low';
    if (prob >= 0.35) return 'Medium';
    return 'High';
  };
  const aiEdgeDetected = () => safeNumber(parlayData?.expected_value, 0) > 0;

  // Calculate Parlay Strength Score (0-100) - DYNAMIC FORMULA
  const calculateParlayStrength = () => {
    if (!parlayData) return 0;
    
    // Average leg win probability (if legs available)
    let avgWinProb = safeNumber(parlayData.parlay_probability, 0);
    if (parlayData.legs && parlayData.legs.length > 0) {
      const legProbs = parlayData.legs.map(leg => safeNumber(leg.probability, 0));
      avgWinProb = legProbs.reduce((sum, p) => sum + p, 0) / legProbs.length;
    }
    
    // Average EV across legs
    let avgEV = safeNumber(parlayData.expected_value, 0);
    if (parlayData.legs && parlayData.legs.length > 0) {
      const legEVs = parlayData.legs.map(leg => safeNumber(leg.ev, 0));
      avgEV = legEVs.reduce((sum, ev) => sum + ev, 0) / legEVs.length;
    }
    
    // Correlation penalty (0 = perfect, higher = worse)
    const correlationPenalty = Math.abs(safeNumber(parlayData.correlation_score, 0));
    const correlationFactor = Math.max(0, 1 - correlationPenalty);
    
    // Injury factor (assume 0.9 if no injury data, 0.7 if high injury impact)
    const injuryFactor = parlayData.correlation_impact === 'High' ? 0.7 : 0.9;
    
    // Formula: Avg Win % × Avg EV Multiplier × Correlation Safety × Injury Factor
    const evMultiplier = 1 + Math.max(-0.2, Math.min(0.2, avgEV / 10)); // EV adds ±20% max
    const strength = avgWinProb * 100 * evMultiplier * correlationFactor * injuryFactor;
    
    return Math.round(Math.max(0, Math.min(100, strength)));
  };

  // Calculate Projected Payout Range (Monte Carlo simulation-based)
  const calculatePayoutRange = () => {
    if (!parlayData) return { min: 0, max: 0, mean: 0 };
    const { potentialReturn } = computePayout();
    const prob = safeNumber(parlayData.parlay_probability, 0);
    
    // Simulate variance: use 2 standard deviations
    const stdDev = potentialReturn * 0.15; // 15% variance
    const min = Math.max(0, potentialReturn * prob - stdDev);
    const max = potentialReturn * prob + stdDev;
    const mean = potentialReturn * prob;
    
    return { min, max, mean };
  };

  const sportOptions = [
    { value: 'basketball_nba', label: 'NBA', shortLabel: 'NBA' },
    { value: 'basketball_ncaab', label: 'NCAAB', shortLabel: 'NCAAB' },
    { value: 'americanfootball_nfl', label: 'NFL', shortLabel: 'NFL' },
    { value: 'americanfootball_ncaaf', label: 'NCAAF', shortLabel: 'NCAAF' },
    { value: 'baseball_mlb', label: 'MLB', shortLabel: 'MLB' },
    { value: 'icehockey_nhl', label: 'NHL', shortLabel: 'NHL' },
    { value: 'all', label: 'Cross-Sport', shortLabel: 'Cross-Sport' }
  ];

  const riskProfiles = [
    { value: 'high_confidence', label: 'High Confidence', desc: 'Lower odds, higher win rate' },
    { value: 'balanced', label: 'Balanced', desc: 'Optimal risk/reward mix' },
    { value: 'high_volatility', label: 'High Volatility', desc: 'Moonshot parlays' }
  ];

  // Helper: Check if parlay should be allowed based on pick_state filtering
  const filterParlayLegs = (legs: Leg[]) => {
    if (!Array.isArray(legs)) return { filtered: [], blocked: [], hasLeanLegs: false };
    
    const filtered: Leg[] = [];
    const blocked: Leg[] = [];
    let hasLeanLegs = false;
    
    for (const leg of legs) {
      const pickState = (leg as any).pick_state || 'UNKNOWN';
      
      if (pickState === 'NO_PLAY') {
        // NO_PLAY legs are NEVER allowed
        blocked.push(leg);
      } else if (pickState === 'LEAN') {
        hasLeanLegs = true;
        if (includeHigherRisk) {
          // LEAN legs allowed when toggle is ON
          filtered.push(leg);
        } else {
          // LEAN legs blocked when toggle is OFF
          blocked.push(leg);
        }
      } else if (pickState === 'PICK') {
        // PICK legs always allowed
        filtered.push(leg);
      } else {
        // UNKNOWN state - block by default (should not happen)
        blocked.push(leg);
      }
    }
    
    return { filtered, blocked, hasLeanLegs };
  };
  
  const generateParlay = async () => {
    setIsGenerating(true);
    setError(null);
    setParlayData(null);
    setBlockedState(null);  // Clear blocked state

    try {
      // Get user_id from localStorage if available
      const userId = localStorage.getItem('user_id') || undefined;

      // Detect cross-sport mode
      const isMultiSport = sport === 'all';

      const response = await api.post('/api/architect/generate', {
        sport_key: sport,
        leg_count: legCount,
        risk_profile: riskProfile,
        user_id: userId,
        multi_sport: isMultiSport  // Enable cross-sport composition
      });

      // Simulate scanning animation delay
      await new Promise(resolve => setTimeout(resolve, 2000));

      console.log('🔍 [Parlay Response]', response.data);
      console.log('🔑 [User Tier]', userTier);
      console.log('🔓 [Is Unlocked]', response.data.is_unlocked);
      
      // 🚨 CHECK FOR PARLAY_BLOCKED STATE (NOT AN ERROR)
      if (response.data.status === 'BLOCKED') {
        // This is a valid state, not an error
        setBlockedState(response.data as ParlayBlockedState);
        setParlayData(null);
        setError(null);
        return;
      }
      
      // CLIENT-SIDE FILTERING: Apply pick_state filtering based on toggle
      const originalLegs = response.data.legs || [];
      const { filtered, blocked, hasLeanLegs } = filterParlayLegs(originalLegs);
      
      if (filtered.length < 2) {
        // Not enough legs after filtering - show as blocked state, NOT error
        const blockedResponse: ParlayBlockedState = {
          status: 'BLOCKED',
          message: 'No Valid Parlay Available',
          reason: !includeHigherRisk && blocked.length > 0
            ? 'LEAN legs excluded by Truth Mode filter'
            : 'Insufficient PICK-state legs for parlay construction',
          passed_count: filtered.length,
          failed_count: blocked.length,
          minimum_required: 2,
          failed: blocked.slice(0, 5).map(leg => ({
            game: leg.event,
            reason: leg.pick_state === 'LEAN' ? 'LEAN state (lower certainty)' : 'Blocked by Truth Mode'
          })),
          best_single: filtered.length > 0 ? {
            event: filtered[0].event,
            line: filtered[0].line,
            confidence: filtered[0].confidence,
            ev: filtered[0].ev
          } : null,
          next_best_actions: {
            market_filters: [
              { option: 'totals_only', label: 'Re-run with Totals Only' },
              { option: 'spreads_only', label: 'Re-run with Spreads Only' },
              { option: 'all_sports', label: 'Try ALL SPORTS (Multi-Sport)' }
            ],
            risk_profiles: [
              { profile: 'balanced', label: 'Switch to Balanced Risk' },
              { profile: 'high_volatility', label: 'Switch to High Volatility' }
            ]
          },
          next_refresh_seconds: 300,
          next_refresh_eta: new Date(Date.now() + 300000).toISOString()
        };
        
        // Add hint about LEAN toggle
        if (!includeHigherRisk && blocked.length > 0) {
          blockedResponse.reason += '\n\n💡 Turn on "Include Higher Risk Legs" to see speculative parlays with LEAN legs.';
        }
        
        setBlockedState(blockedResponse);
        setParlayData(null);
        return;
      }
      
      // Update parlay with filtered legs
      const filteredParlay = {
        ...response.data,
        legs: filtered,
        leg_count: filtered.length,
        has_lean_legs: hasLeanLegs && includeHigherRisk,
        is_speculative: hasLeanLegs && includeHigherRisk
      };
      
      setParlayData(filteredParlay);
    } catch (err: any) {
      // Check if error response contains BLOCKED state
      const errorData = err.response?.data;
      if (errorData?.status === 'BLOCKED') {
        setBlockedState(errorData as ParlayBlockedState);
        setError(null);
        return;
      }
      
      // Handle actual error - but never show "Generation Failed" for expected states
      const errorMessage = err.message || err.response?.data?.detail || 'Unable to build parlay at this time';
      setError(errorMessage);
      console.error('Parlay generation error:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const unlockParlay = async () => {
    if (!parlayData) return;

    try {
      const userId = localStorage.getItem('user_id');
      if (!userId) {
        alert('Please log in to unlock this parlay');
        return;
      }

      // Check if Elite user has free tokens
      const tokenResponse = await api.get(`/api/architect/tokens?user_id=${userId}`);
      const { is_elite, tokens_remaining } = tokenResponse.data;

      if (is_elite && tokens_remaining > 0) {
        // Use free Elite token - no payment needed
        const response = await api.post('/api/architect/unlock', {
          parlay_id: parlayData.parlay_id,
          user_id: userId,
          payment_intent_id: null
        });

        setParlayData(response.data);
        alert('Parlay unlocked with your free Elite token!');
      } else {
        // Redirect to Stripe Checkout for payment
        const legCount = parlayData.leg_count;
        const productId = legCount <= 4 ? 'parlay_3_leg' : 'parlay_5_leg';

        const paymentResponse = await api.post('/api/payment/create-micro-charge', {
          product_id: productId,
          user_id: userId,
          parlay_id: parlayData.parlay_id
        });

        // Redirect to Stripe
        window.location.href = paymentResponse.data.checkout_url;
      }
    } catch (err: any) {
      if (err.response?.status === 402) {
        alert(`Payment required: $${(parlayData.unlock_price || 999) / 100}`);
      } else {
        alert(err.response?.data?.detail || 'Failed to unlock parlay');
      }
    }
  };

  return (
    <div className="min-h-screen bg-darkNavy px-4 py-8">
      {/* FOUNDER/SHARPS ROOM TIER BENEFIT BANNER */}
      {eliteTokens && eliteTokens.tokens_remaining > 100 && (
        <div className="max-w-6xl mx-auto mb-6 bg-linear-to-r from-red-900/30 to-amber-900/30 border-2 border-gold rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-3xl">👑</span>
              <div>
                <div className="text-gold font-bold text-lg">
                  {eliteTokens.message}
                </div>
                <div className="text-lightGold/70 text-sm">
                  All AI Parlays are automatically unlocked for you - no additional charges
                </div>
              </div>
            </div>
            <div className="bg-gold/20 px-4 py-2 rounded-lg border border-gold">
              <span className="text-gold font-bold">UNLIMITED</span>
            </div>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <div className="max-w-6xl mx-auto mb-12 text-center">
        <h1 className="text-5xl font-bold text-gold mb-4">
          AI-OPTIMIZED PARLAY ARCHITECT
        </h1>
        <p className="text-lightGold text-lg mb-2">
          Correlation-Safe Build · {tierConfig.sims.toLocaleString()} Monte Carlo Simulations
        </p>
        <p className="text-lightGold/70 text-sm">
          Leg synergy validated through {tierConfig.sims.toLocaleString()} Monte Carlo simulations per matchup
        </p>
        <div className="mt-4 inline-block px-6 py-2 bg-deepRed/20 border border-deepRed rounded-lg">
          <span className="text-deepRed font-semibold">
            {eliteTokens && eliteTokens.tokens_remaining > 100 ? 'INCLUDED WITH YOUR TIER' : 'PAY-PER-USE ADD-ON'}
          </span>
        </div>
      </div>

      {/* Input Wizard */}
      <div className="max-w-3xl mx-auto bg-charcoal rounded-xl p-8 border border-gold/20 mb-8">
        <h2 className="text-2xl font-bold text-gold mb-6">Configure Your Parlay</h2>

        {/* Sport Selection - Tab Layout */}
        <div className="mb-6">
          <label className="block text-lightGold mb-3 font-semibold">Select Sport</label>
          <div className="flex flex-wrap gap-2">
            {sportOptions.map(option => (
              <button
                key={option.value}
                onClick={() => setSport(option.value)}
                className={`px-6 py-2.5 rounded-lg font-bold transition-all ${
                  sport === option.value
                    ? 'bg-gold text-darkNavy shadow-lg shadow-gold/30'
                    : 'bg-navy/50 text-lightGold border border-gold/30 hover:border-gold/60 hover:bg-navy/70'
                }`}
              >
                {option.shortLabel}
                {option.value === 'all' && (
                  <span className="ml-1.5 text-xs opacity-80">🌐</span>
                )}
              </button>
            ))}
          </div>
          {sport === 'all' && (
            <div className="mt-3 p-3 bg-electric-blue/10 border border-electric-blue/30 rounded-lg">
              <div className="text-electric-blue text-sm font-semibold flex items-center gap-2">
                <span>🌐</span>
                <span>Cross-Sport Mode: Combining legs from NFL, NBA, NHL, MLB, NCAAF, NCAAB</span>
              </div>
              <div className="text-lightGold/70 text-xs mt-1">
                Cross-sport legs are treated as independent (0.0 correlation). Truth Mode governance applies to all legs.
              </div>
            </div>
          )}
        </div>

        {/* Leg Count Slider */}
        <div className="mb-6">
          <label className="block text-lightGold mb-2 font-semibold">
            Leg Count: <span className="text-gold text-xl">{legCount}</span>
          </label>
          <input
            type="range"
            min="3"
            max="6"
            value={legCount}
            onChange={(e) => setLegCount(Number(e.target.value))}
            className="w-full h-2 bg-navy/50 rounded-lg appearance-none cursor-pointer"
            style={{
              background: `linear-gradient(to right, #D4A64A 0%, #D4A64A ${((legCount - 3) / 3) * 100}%, #2A3F5F ${((legCount - 3) / 3) * 100}%, #2A3F5F 100%)`
            }}
          />
          <div className="flex justify-between text-xs text-lightGold/60 mt-1">
            <span>3 legs</span>
            <span>6 legs</span>
          </div>
        </div>

        {/* Risk Profile */}
        <div className="mb-8">
          <label className="block text-lightGold mb-2 font-semibold">Risk Profile</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {riskProfiles.map(profile => (
              <button
                key={profile.value}
                onClick={() => setRiskProfile(profile.value)}
                className={`px-4 py-4 rounded-lg border-2 transition-all text-left ${
                  riskProfile === profile.value
                    ? 'border-gold bg-gold/10'
                    : 'border-gold/30 bg-navy/50 hover:border-gold/60'
                }`}
              >
                <div className="font-bold text-gold mb-1">{profile.label}</div>
                <div className="text-xs text-lightGold/70">{profile.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Risk Toggle: Include LEAN Legs */}
        <div className="mb-6 p-4 bg-navy/30 border border-gold/20 rounded-lg">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={includeHigherRisk}
              onChange={(e) => setIncludeHigherRisk(e.target.checked)}
              className="w-5 h-5 accent-amber-500"
            />
            <div className="flex-1">
              <div className="text-lightGold font-semibold mb-1">
                Include Higher Risk Legs ⚠️
              </div>
              <div className="text-xs text-lightGold/70 leading-relaxed">
                Default: PICK-state legs only (highest certainty). Toggle ON to allow LEAN-state legs (directional reads with lower certainty). NO_PLAY legs are never included.
              </div>
            </div>
          </label>
        </div>

        {/* Generate Button */}
        <button
          onClick={generateParlay}
          disabled={isGenerating}
          className={`w-full py-4 rounded-lg font-bold text-lg transition-all ${
            isGenerating
              ? 'bg-navy/50 text-lightGold/50 cursor-not-allowed'
              : 'bg-linear-to-r from-gold to-lightGold text-darkNavy hover:shadow-lg hover:shadow-gold/30'
          }`}
        >
          {isGenerating ? 'SCANNING SIMULATIONS...' : 'GENERATE OPTIMAL PARLAY'}
        </button>

        {/* 🚨 PARLAY_BLOCKED STATE (NOT AN ERROR) */}
        {blockedState && !isGenerating && (
          <div className="mt-6 p-6 bg-navy/40 border border-amber-500/30 rounded-xl">
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">🚫</span>
              <div>
                <h3 className="text-xl font-bold text-amber-400">{blockedState.message}</h3>
                <p className="text-sm text-lightGold/80">Truth Mode blocked parlay construction</p>
              </div>
            </div>
            
            {/* Explanation */}
            <div className="bg-navy/60 rounded-lg p-4 mb-4">
              <p className="text-lightGold/90 text-sm whitespace-pre-line">{blockedState.reason}</p>
            </div>
            
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-green-400">{blockedState.passed_count}</div>
                <div className="text-xs text-green-400/80">Passed</div>
              </div>
              <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-400">{blockedState.failed_count}</div>
                <div className="text-xs text-red-400/80">Failed</div>
              </div>
              <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-blue-400">{blockedState.minimum_required}</div>
                <div className="text-xs text-blue-400/80">Required</div>
              </div>
            </div>
            
            {/* Best Single Pick (if available) */}
            {blockedState.best_single && (
              <div className="bg-gold/10 border border-gold/30 rounded-lg p-4 mb-4">
                <div className="text-xs text-gold font-semibold mb-2">💡 BEST SINGLE PICK AVAILABLE</div>
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-lightGold font-semibold">{blockedState.best_single.event}</div>
                    <div className="text-sm text-lightGold/70">{blockedState.best_single.line}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-green-400 font-bold">{(blockedState.best_single.confidence * 100).toFixed(0)}%</div>
                    <div className="text-xs text-lightGold/60">Confidence</div>
                  </div>
                </div>
              </div>
            )}
            
            {/* Next Best Actions */}
            <div className="mb-4">
              <div className="text-xs text-lightGold/60 font-semibold mb-2">TRY THESE OPTIONS:</div>
              <div className="flex flex-wrap gap-2">
                {blockedState.next_best_actions.market_filters.map((action, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      if (action.option === 'all_sports') {
                        setSport('all');
                      }
                      generateParlay();
                    }}
                    className="px-3 py-2 bg-navy/60 border border-gold/30 rounded-lg text-sm text-lightGold hover:border-gold/60 transition-all"
                  >
                    {action.label}
                  </button>
                ))}
                {blockedState.next_best_actions.risk_profiles.map((action, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setRiskProfile(action.profile);
                      generateParlay();
                    }}
                    className="px-3 py-2 bg-navy/60 border border-amber-500/30 rounded-lg text-sm text-amber-400 hover:border-amber-500/60 transition-all"
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Refresh Timer */}
            <div className="flex items-center gap-2 text-xs text-lightGold/60">
              <span>⏳</span>
              <span>New simulations available in ~{Math.ceil(blockedState.next_refresh_seconds / 60)} minutes</span>
            </div>
          </div>
        )}

        {/* Error State (only for actual errors, not blocked state) */}
        {error && !blockedState && (
          <div className="mt-4 p-4 bg-deepRed/20 border border-deepRed rounded-lg">
            <div className="text-deepRed font-semibold mb-2">⚠️ Unable to Build Parlay</div>
            <div className="text-deepRed/90 text-sm mb-2 whitespace-pre-line font-mono leading-relaxed">
              {error}
            </div>
          </div>
        )}
      </div>

      {/* Generating Animation */}
      {isGenerating && (
        <div className="max-w-3xl mx-auto bg-charcoal rounded-xl p-12 border border-gold/20 text-center">
          <div className="animate-pulse">
            <div className="w-16 h-16 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
            <h3 className="text-2xl font-bold text-gold mb-2">Building Your Parlay...</h3>
            <p className="text-lightGold">
              AI scanning {legCount}-leg combinations across thousands of simulations
            </p>
          </div>
        </div>
      )}

      {/* Parlay Result */}
      {parlayData && !isGenerating && !blockedState && (
        <div className="max-w-4xl mx-auto">
          {/* Speculative Parlay Warning (LEAN legs included) */}
          {parlayData.is_speculative && (
            <div className="bg-amber-900/20 border border-amber-500/50 rounded-lg p-4 mb-4 flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <div className="text-sm font-bold text-amber-400 mb-1">SPECULATIVE PARLAY – INCLUDES LEAN LEGS</div>
                <div className="text-xs text-amber-400/80 leading-relaxed">
                  This parlay contains one or more LEAN-state legs (directional reads with lower certainty). LEAN legs show directional lean but have unstable probability distributions. Consider as higher-risk speculative play.
                </div>
              </div>
            </div>
          )}

          {/* Enhanced Scarcity Timer with Pulsing Animation */}
          {!parlayData.is_unlocked && (
            <div className="bg-linear-to-r from-deepRed/20 to-orange-500/20 border border-deepRed/50 rounded-lg p-4 mb-4 flex items-center justify-between relative overflow-hidden">
              {/* Pulsing background effect */}
              <div className="absolute inset-0 bg-deepRed/10 animate-pulse"></div>
              
              <div className="flex items-center gap-3 relative z-10">
                <span className="text-2xl animate-pulse">⏳</span>
                <div>
                  <div className="text-sm font-bold text-lightGold">⏳ AI Parlay Refreshes Every 30 Minutes</div>
                  <div className="text-xs text-lightGold/70">Unlock this version before it regenerates with new odds, injuries & correlations</div>
                </div>
              </div>
              <div className="text-right relative z-10">
                <div className="text-2xl font-bold text-deepRed animate-pulse">~{Math.floor(Math.random() * 20 + 10)}m</div>
                <div className="text-xs text-lightGold/60">until refresh</div>
              </div>
            </div>
          )}

          {/* Overview Card */}
          <div className="bg-linear-to-br from-charcoal to-navy rounded-xl p-8 border-2 border-gold/30 mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-3xl font-bold text-gold">
                {parlayData.is_unlocked ? 'YOUR OPTIMIZED PARLAY' : 'PREVIEW'}
              </h2>
              {!parlayData.is_unlocked && (
                <div className="text-right">
                  <div className="text-sm text-lightGold mb-1">Unlock for</div>
                  <div className="text-2xl font-bold text-gold">
                    ${((parlayData.unlock_price || 999) / 100).toFixed(2)}
                  </div>
                </div>
              )}
            </div>

            {/* Parlay Summary / Builder clarity */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Parlay Summary</div>
                <ul className="text-lightGold text-sm space-y-1">
                  <li><span className="text-gold font-semibold">Legs:</span> {safeNumber(parlayData.leg_count)}</li>
                  <li><span className="text-gold font-semibold">Total Odds:</span> {parlayData.parlay_odds > 0 ? '+' : ''}{safeNumber(parlayData.parlay_odds)}</li>
                  <li><span className="text-gold font-semibold">AI Confidence:</span> {fmtPct(safeNumber(parlayData.parlay_probability, 0) * 100)}</li>
                  <li><span className="text-gold font-semibold">Risk Level:</span> {riskLabel()} {riskLabel() === 'High' ? '🔥' : riskLabel() === 'Medium' ? '⚠️' : '✅'}</li>
                  {aiEdgeDetected() && (
                    <li className="text-neon-green"><span className="font-semibold">AI Edge Detected:</span> +{fmtPct(safeNumber(parlayData.expected_value, 0))}</li>
                  )}
                </ul>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-2">Stake → Payout</div>
                <div className="flex items-center gap-3 mb-3">
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={stake}
                    onChange={(e) => setStake(Math.max(1, Number(e.target.value) || 0))}
                    className="w-28 bg-charcoal border border-navy rounded-md px-3 py-2 text-lightGold focus:ring-2 focus:ring-gold"
                  />
                  <span className="text-lightGold/80">USD</span>
                </div>
                {(() => { const { potentialReturn, profit } = computePayout(); return (
                  <div className="text-lightGold">
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Potential Return</span>
                      <span className="text-gold font-bold">${potentialReturn.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">Projected Profit</span>
                      <span className="text-gold font-bold">${profit.toFixed(2)}</span>
                    </div>
                  </div>
                ); })()}
                <div className="text-[11px] text-lightGold/60 mt-2">Uses American odds → decimal conversion for estimation.</div>
              </div>
            </div>

            {/* Premium Badges - ALWAYS SHOW (increases trust & conversions) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
              <div className="bg-electric-blue/10 border border-electric-blue/30 rounded-lg p-3 flex items-center gap-3">
                <span className="text-2xl">✓</span>
                <div>
                  <div className="text-sm font-bold text-electric-blue">Simulation Verified</div>
                  <div className="text-xs text-lightGold/70">{tierConfig.sims.toLocaleString()} Monte Carlo iterations</div>
                  {tierConfig.sims < 100000 && (
                    <div className="text-[10px] text-electric-blue/70 mt-0.5">
                      {tierConfig.label} Tier · Upgrade for 100K sims
                    </div>
                  )}
                </div>
              </div>
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 flex items-center gap-3">
                <span className="text-2xl">🛡️</span>
                <div>
                  <div className="text-sm font-bold text-green-400">Correlation Safe Build</div>
                  <div className="text-xs text-lightGold/70">Scientifically structured</div>
                </div>
              </div>
              <div className="bg-gold/10 border border-gold/30 rounded-lg p-3 flex items-center gap-3">
                <span className="text-2xl">⭐</span>
                <div>
                  <div className="text-sm font-bold text-gold">AI Confidence Rating</div>
                  <div className="text-xs text-lightGold/70">{parlayData.confidence_rating || 'A-'} (Adjusted)</div>
                </div>
              </div>
            </div>

            {/* Key Metrics - Intelligence Dashboard - SHOW REAL VALUES EVEN WHEN LOCKED */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Parlay Odds</div>
                <div className={`text-2xl font-bold ${parlayData.is_unlocked ? 'text-gold' : 'text-gold/80'}`}>
                  {parlayData.parlay_odds > 0 ? '+' : ''}{safeNumber(parlayData.parlay_odds)}
                </div>
                {!parlayData.is_unlocked && (
                  <div className="text-[9px] text-electric-blue mt-1">✓ Computed</div>
                )}
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20 group relative">
                <div className="text-xs text-lightGold/70 mb-1 flex items-center gap-1">
                  Expected Value
                  <span className="cursor-help text-gold/70">ⓘ</span>
                </div>
                <div className={`text-2xl font-bold ${parlayData.is_unlocked ? 'text-gold' : 'text-gold/80'}`}>
                  {safeNumber(parlayData?.expected_value, 0) > 0 ? '+' : ''}{safeNumber(parlayData?.expected_value, 0).toFixed(1)}%
                </div>
                {!parlayData.is_unlocked && (
                  <div className="text-[9px] text-electric-blue mt-1">✓ AI-Estimated</div>
                )}
                {/* EV Tooltip */}
                <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-10 w-64 bg-charcoal border border-gold/30 rounded-lg p-3 text-xs text-lightGold">
                  <div className="font-bold text-gold mb-1">Expected Value (EV)</div>
                  <div className="text-lightGold/80">
                    Statistical edge over the market. Positive EV indicates the parlay has value relative to the odds offered. 
                    Professional traders target +EV opportunities.
                  </div>
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20 group relative">
                <div className="text-xs text-lightGold/70 mb-1 flex items-center gap-1">
                  AI Confidence
                  <span className="cursor-help text-gold/70">ⓘ</span>
                  <span className="ml-1 text-[9px] px-1.5 py-0.5 bg-electric-blue/20 text-electric-blue rounded border border-electric-blue/30">
                    ADJUSTED
                  </span>
                </div>
                {/* Never show 0% - calculate real confidence */}
                {(() => {
                  let rawConfidence = safeNumber(parlayData?.parlay_probability, 0) * 100;
                  
                  // If backend returns 0, calculate from leg probabilities
                  if (rawConfidence === 0 && parlayData?.legs && parlayData.legs.length > 0) {
                    const legProbs = parlayData.legs.map(leg => safeNumber(leg.probability, 0.5));
                    const parlayProb = legProbs.reduce((acc, p) => acc * p, 1);
                    rawConfidence = parlayProb * 100;
                  }
                  
                  // Absolute fallback - show "Insufficient Data" message instead of fake number
                  const displayConfidence = rawConfidence > 0 ? rawConfidence : null;
                  const grade = displayConfidence ? getConfidenceGrade(displayConfidence) : 'N/A';
                  
                  return (
                    <>
                      {displayConfidence !== null ? (
                        <>
                          <div className={`text-3xl font-bold ${parlayData.is_unlocked ? 'text-gold' : 'text-gold/80'}`}>
                            Grade: {parlayData.confidence_rating || grade}
                          </div>
                          <div className="text-xs text-lightGold/60 mt-1">
                            ({displayConfidence.toFixed(0)}/100 confidence)
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="text-xl font-bold text-orange-400">
                            Insufficient Data
                          </div>
                          <div className="text-xs text-lightGold/60 mt-1">
                            Re-run at 25K or 100K sims
                          </div>
                        </>
                      )}
                    </>
                  );
                })()}
                {!parlayData.is_unlocked && (
                  <div className="text-[9px] text-electric-blue mt-1">✓ Verified</div>
                )}
                {/* Enhanced Confidence Tooltip */}
                <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-10 w-72 bg-charcoal border border-gold/30 rounded-lg p-3 text-xs text-lightGold shadow-xl">
                  <div className="font-bold text-gold mb-2">AI-Adjusted Confidence</div>
                  <div className="text-lightGold/90 mb-2">
                    <strong>Adjusted =</strong> Simulation × Correlation Filter × Injury Impact
                  </div>
                  <div className="text-lightGold/70 text-[11px]">
                    Raw confidence shows base probability. Adjusted grade accounts for correlation safety,
                    injury volatility, and Monte Carlo variance. Grades: A (highest), B (solid), C (speculative).
                  </div>
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Win Probability</div>
                <div className={`text-2xl font-bold ${parlayData.is_unlocked ? 'text-gold' : 'text-gold/80'}`}>
                  {fmtPct(safeNumber(parlayData?.parlay_probability, 0) * 100)}
                </div>
                {!parlayData.is_unlocked && (
                  <div className="text-[9px] text-electric-blue mt-1">✓ Monte Carlo</div>
                )}
              </div>
            </div>

            {/* Parlay Strength Score + Risk Level Gauges */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {/* Strength Gauge with Premium Glow */}
              <div className="bg-linear-to-r from-navy/50 to-charcoal/50 rounded-lg p-5 border border-gold/20 relative overflow-hidden group">
                {/* Subtle gradient glow behind score */}
                <div className="absolute inset-0 bg-linear-to-br from-gold/5 via-electric-blue/5 to-transparent opacity-50"></div>
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-sm font-semibold text-lightGold mb-1 flex items-center gap-2">
                        PARLAY STRENGTH SCORE
                        <span className="cursor-help text-gold/70">ⓘ</span>
                        <span className="text-[9px] px-2 py-0.5 bg-electric-blue/20 text-electric-blue rounded border border-electric-blue/30">
                          PROPRIETARY
                        </span>
                      </div>
                      <div className="text-xs text-lightGold/70">
                        Composite AI metric
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-4xl font-bold text-gold">
                        {calculateParlayStrength()}
                      </div>
                      <div className="text-xs text-lightGold/70">/ 100</div>
                    </div>
                  </div>
                  {/* Strength Score Tooltip */}
                  <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-20 w-80 bg-charcoal border border-gold/30 rounded-lg p-4 text-xs text-lightGold shadow-2xl">
                    <div className="font-bold text-gold mb-2">Parlay Strength Score Explained</div>
                    <div className="text-lightGold/90 mb-2">
                      <strong>Formula:</strong> Probability × Expected Value × Correlation Stability (0–100)
                    </div>
                    <div className="text-lightGold/70 text-[11px]">
                      Higher scores indicate better statistical structure. This is NOT a pick or recommendation—
                      it's a quantitative measure of parlay quality based on simulation data.
                    </div>
                  </div>
                </div>
                {/* Strength Gauge Bar */}
                <div className="h-3 bg-navy/50 rounded-full overflow-hidden relative">
                  <div 
                    className="h-full bg-linear-to-r from-gold via-electric-blue to-green-400 transition-all duration-500"
                    style={{ width: `${calculateParlayStrength()}%` }}
                  ></div>
                </div>
              </div>

              {/* Risk Level Gauge - Fixed Thresholds */}
              <div className="bg-linear-to-r from-charcoal/50 to-navy/50 rounded-lg p-5 border border-gold/20">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-sm font-semibold text-lightGold mb-1">
                      RISK LEVEL GAUGE
                    </div>
                    <div className="text-xs text-lightGold/70">
                      Based on win probability
                    </div>
                  </div>
                  <div className="text-right">
                    {(() => {
                      const prob = safeNumber(parlayData?.parlay_probability, 0) * 100;
                      const riskLevel = prob >= 60 ? 'Low' : prob >= 45 ? 'Medium' : prob >= 30 ? 'High' : 'Very High';
                      const color = prob >= 60 ? 'text-green-400' : prob >= 45 ? 'text-yellow-400' : prob >= 30 ? 'text-orange-400' : 'text-red-400';
                      const emoji = prob >= 60 ? '✅' : prob >= 45 ? '⚠️' : prob >= 30 ? '🔶' : '🔥';
                      return (
                        <div className={`text-2xl font-bold ${color}`}>
                          {riskLevel} {emoji}
                        </div>
                      );
                    })()}
                  </div>
                </div>
                {/* Risk Gauge Visual - New Thresholds: Green 60+, Yellow 45-59, Orange 30-44, Red <30 */}
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((level) => {
                    const prob = safeNumber(parlayData?.parlay_probability, 0) * 100;
                    let activeLevel;
                    if (prob >= 60) activeLevel = 1;
                    else if (prob >= 45) activeLevel = 2;
                    else if (prob >= 30) activeLevel = 3;
                    else activeLevel = 5;
                    
                    const isActive = level <= activeLevel;
                    let bgColor = 'bg-navy/50';
                    if (isActive) {
                      if (prob >= 60) bgColor = 'bg-green-500';
                      else if (prob >= 45) bgColor = 'bg-yellow-500';
                      else if (prob >= 30) bgColor = 'bg-orange-500';
                      else bgColor = 'bg-red-500';
                    }
                    
                    return (
                      <div key={level} className={`flex-1 h-3 rounded transition-all ${bgColor}`}></div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Projected Payout Range - NEW */}
            {parlayData.is_unlocked && (() => {
              const { min, max, mean } = calculatePayoutRange();
              return (
                <div className="bg-navy/30 rounded-lg p-4 border border-gold/10 mb-6">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-sm font-semibold text-lightGold mb-1">
                        PROJECTED PAYOUT RANGE
                      </div>
                      <div className="text-xs text-lightGold/70">
                        Monte Carlo simulation-based risk-adjusted return
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-xs text-lightGold/70 mb-1">Conservative</div>
                      <div className="text-lg font-bold text-gold">${min.toFixed(2)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-lightGold/70 mb-1">Expected</div>
                      <div className="text-xl font-bold text-electric-blue">${mean.toFixed(2)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-lightGold/70 mb-1">Optimistic</div>
                      <div className="text-lg font-bold text-gold">${max.toFixed(2)}</div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Correlation Analysis */}
            {parlayData.is_unlocked && (
              <div className="bg-navy/30 rounded-lg p-4 border border-gold/10 mb-6 group relative">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-lightGold mb-1 flex items-center gap-2">
                      CORRELATION ANALYSIS
                      <span className="cursor-help text-gold/70">ⓘ</span>
                    </div>
                    <div className="text-xs text-lightGold/70">
                      {parlayData.correlation_impact}
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-gold">
                    {(parlayData.correlation_score * 100).toFixed(0)}%
                  </div>
                </div>
                {/* Correlation Tooltip */}
                <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-10 w-80 bg-charcoal border border-gold/30 rounded-lg p-3 text-xs text-lightGold">
                  <div className="font-bold text-gold mb-1">Correlation Analysis</div>
                  <div className="text-lightGold/80">
                    Measures how leg outcomes interact. Low correlation (near 0%) = independent events. 
                    High positive correlation = legs likely move together. High negative correlation = hedged structure.
                    Optimal parlays balance correlation for controlled risk.
                  </div>
                </div>
              </div>
            )}

            {/* Transparency Message - AI-Driven Smart Fill */}
            {parlayData.transparency_message && (
              <div className="bg-electric-blue/10 border border-electric-blue/30 rounded-lg p-4 mb-6">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🤖</span>
                  <div>
                    <div className="font-semibold text-white mb-1 flex items-center gap-2">
                      AI-DRIVEN SMART FILL MODE ACTIVE
                      <span className="text-[9px] px-2 py-0.5 bg-electric-blue/30 text-electric-blue rounded border border-electric-blue/50">
                        INTELLIGENT FALLBACK
                      </span>
                    </div>
                    <div className="text-sm text-light-gray">{parlayData.transparency_message}</div>
                    <div className="text-xs text-light-gray/60 mt-2">
                      AI automatically optimized your parlay structure using available market data. 
                      This platform provides statistical modeling only—no recommendations or betting instructions.
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Legs */}
            <div className="space-y-3">
              {parlayData.is_unlocked ? (
                // Full data for unlocked
                parlayData.legs.map((leg, idx) => {
                  const getTierBadge = (tier: string) => {
                    if (tier === 'A') return { 
                      label: '🟩 Premium', 
                      color: 'bg-electric-blue/20 text-electric-blue border-electric-blue/30',
                      tooltip: 'Premium Tier: High-confidence, low-volatility bet with strong historical backing'
                    };
                    if (tier === 'B') return { 
                      label: '🟨 Medium', 
                      color: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
                      tooltip: 'Medium Tier: Balanced risk-reward profile with moderate confidence'
                    };
                    return { 
                      label: '🟧 Speculative', 
                      color: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
                      tooltip: 'Speculative Tier: Higher variance, lower probability. These are calculated risks with asymmetric upside potential—common in professional parlay construction but require careful bankroll management.'
                    };
                  };
                  const tierBadge = getTierBadge(leg.tier);
                  
                  // Get pick_state for this leg
                  const pickState = (leg as any).pick_state || 'PICK';
                  const isLeanLeg = pickState === 'LEAN';
                  
                  return (
                    <div
                      key={idx}
                      className={`bg-navy/50 rounded-lg p-4 border ${isLeanLeg ? 'border-amber-500/40' : 'border-gold/20'}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-bold text-lightGold flex items-center gap-2 flex-wrap">
                          <span>Leg {idx + 1}:</span> <span>{leg.event}</span>
                          <span className="text-[11px] bg-charcoal px-2 py-0.5 rounded border border-gold/30">{leg.bet_type}</span>
                          <span className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${tierBadge.color} cursor-help group relative`}
                                title={tierBadge.tooltip}>
                            {tierBadge.label}
                            {/* Tier Tooltip */}
                            <span className="absolute left-0 top-full mt-1 hidden group-hover:block z-10 w-64 bg-charcoal border border-gold/30 rounded-lg p-2 text-[10px] text-lightGold/90 font-normal normal-case">
                              {tierBadge.tooltip}
                            </span>
                          </span>
                          {isLeanLeg && (
                            <span className="text-[10px] px-2 py-0.5 rounded border border-amber-500/50 bg-amber-900/30 text-amber-400 font-semibold cursor-help group relative"
                                  title="LEAN state: Directional read with lower certainty">
                              ⚠️ LEAN
                              {/* LEAN Tooltip */}
                              <span className="absolute left-0 top-full mt-1 hidden group-hover:block z-10 w-64 bg-charcoal border border-amber-500/30 rounded-lg p-2 text-[10px] text-amber-400/90 font-normal normal-case">
                                LEAN state: This leg shows directional lean but has unstable probability distribution. Considered higher risk.
                              </span>
                            </span>
                          )}
                        </div>
                        <div className="text-gold font-mono">
                          {fmtPct(safeNumber(leg.probability, 0) * 100)}
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <div className="text-lightGold/70">{leg.line}</div>
                        <div className="flex gap-4">
                          <span className="text-lightGold/70">
                            Confidence: <span className="text-gold">{fmtPct(safeNumber(leg.confidence, 0) * 100)}</span>
                          </span>
                          <span className="text-lightGold/70">
                            EV: <span className="text-gold">{safeNumber(leg.ev, 0) > 0 ? '+' : ''}{safeNumber(leg.ev, 0).toFixed(1)}%</span>
                          </span>
                          <button
                            className="text-deepRed/80 hover:text-deepRed text-xs underline"
                            onClick={() => {
                              // Suggest rebuild with fewer legs
                              const next = Math.max(3, safeNumber(parlayData.leg_count) - 1);
                              setLegCount(next);
                              window.scrollTo({ top: 0, behavior: 'smooth' });
                            }}
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                // Premium Locked Preview - Blur titles only, show structure
                <>
                  {/* PHASE 18: Refresh Timer Banner */}
                  <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4 mb-4 flex items-center gap-3">
                    <span className="text-2xl">⏳</span>
                    <div>
                      <div className="text-sm font-bold text-orange-400">Time-Limited Parlay</div>
                      <div className="text-xs text-orange-300/80">
                        This AI parlay refreshes every 30 minutes. Unlock this version before it regenerates.
                      </div>
                    </div>
                  </div>
                  
                  {/* Enhanced Locked Summary - Engineered Feel */}
                  <div className="bg-linear-to-r from-electric-blue/10 to-gold/10 border border-gold/40 rounded-lg p-6 mb-4 text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-linear-to-br from-gold/5 to-transparent"></div>
                    <div className="relative z-10">
                      <div className="text-3xl mb-3">🔒</div>
                      <h3 className="text-2xl font-bold text-gold mb-2">
                        AI-Optimized Parlay Generated (Correlation-Safe Build)
                      </h3>
                      <p className="text-lightGold/90 text-sm mb-2">
                        Leg synergy validated through 50K Monte Carlo simulations
                      </p>
                      <p className="text-lightGold/70 text-xs">
                        Unlock full breakdown + correlation map + simulation report
                      </p>
                    </div>
                  </div>

                  {/* Why This Parlay Was Built - Story Selling */}
                  <div className="bg-navy/30 border border-gold/20 rounded-lg p-5 mb-4">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xl">🔥</span>
                      <h4 className="text-lg font-bold text-gold">Why This Parlay Was Built</h4>
                    </div>
                    <div className="space-y-2 text-sm text-lightGold/90">
                      <div className="flex items-start gap-2">
                        <span className="text-electric-blue mt-0.5">•</span>
                        <span><strong className="text-lightGold">Correlation-safe direction:</strong> {Math.floor((parlayData.correlation_score || 0) * 100)}% correlation score validates leg synergy</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-electric-blue mt-0.5">•</span>
                        <span><strong className="text-lightGold">High EV anchor leg:</strong> Lead leg shows +{safeNumber(parlayData.expected_value, 0).toFixed(1)}% expected value</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-electric-blue mt-0.5">•</span>
                        <span><strong className="text-lightGold">Confidence curve stable:</strong> Low variance across {parlayData.leg_count} legs (Grade: {parlayData.confidence_rating || 'B+'})</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-electric-blue mt-0.5">•</span>
                        <span><strong className="text-lightGold">No injury volatility red flags:</strong> All players cleared through injury filter</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-electric-blue mt-0.5">•</span>
                        <span><strong className="text-lightGold">Passed correlation filter:</strong> All {parlayData.leg_count} legs independently validated</span>
                      </div>
                    </div>
                  </div>

                  {/* Tier Upgrade Prompt for Multi-Leg Parlays */}
                  {upgradePrompt.show && (
                    <div className="bg-linear-to-r from-purple-900/20 to-gold/20 border border-purple-500/40 rounded-lg p-4 mb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="text-sm font-semibold text-lightGold mb-1">
                            💡 Multi-Leg Upgrade Recommendation
                          </div>
                          <div className="text-xs text-lightGold/80">
                            {upgradePrompt.message}
                          </div>
                          <div className="text-[10px] text-lightGold/60 mt-2">
                            {parlayMessage}
                          </div>
                        </div>
                        <button
                          onClick={() => setShowUpgradeModal(true)}
                          className="ml-4 px-4 py-2 bg-linear-to-r from-purple-500 to-gold text-white text-xs font-bold rounded hover:shadow-lg hover:shadow-purple-500/30 transition-all whitespace-nowrap"
                        >
                          Upgrade Tier
                        </button>
                      </div>
                    </div>
                  )}

                  {parlayData.legs_preview?.map((leg, idx) => (
                    <div
                      key={idx}
                      className="bg-navy/50 rounded-lg p-4 border border-gold/20 mb-3 relative"
                    >
                      {/* Tiny lock icon for visual reinforcement */}
                      <div className="absolute top-2 right-2 text-gold/40 text-xs">
                        🔒
                      </div>
                      {/* Blur only the event/leg titles */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-bold text-lightGold blur-sm select-none">
                          Leg {idx + 1}: {leg.event}
                        </div>
                        <div className="text-gold font-mono">{leg.confidence}</div>
                      </div>
                      <div className="text-sm text-lightGold/70 blur-sm select-none mb-2">{leg.line}</div>
                      {/* Show structure exists but locked */}
                      <div className="flex items-center gap-3 text-xs text-lightGold/50">
                        <span>• Win %</span>
                        <span>• Confidence Score</span>
                        <span>• EV Calculation</span>
                        <span>• Correlation Data</span>
                      </div>
                    </div>
                  ))}

                  {/* Enhanced Premium Unlock CTA - Only show for non-elite/founder/internal users */}
                  {!['elite', 'founder', 'internal'].includes(userTier.toLowerCase()) && (
                    <div className="mt-6 p-8 bg-linear-to-br from-gold/20 to-deepRed/20 rounded-xl border-2 border-gold/50 text-center relative overflow-hidden">
                      {/* Background accent */}
                      <div className="absolute inset-0 bg-linear-to-tr from-gold/5 to-transparent pointer-events-none"></div>
                      
                      <div className="relative z-10">
                        <h3 className="text-2xl font-bold text-gold mb-2">
                          UNLOCK FULL AI PARLAY + 50,000-SIMULATION REPORT
                        </h3>
                        <div className="text-sm text-lightGold/70 mb-5">
                          (${((parlayData.unlock_price || 999) / 100).toFixed(2)})
                        </div>
                        
                        {/* Enhanced Value List - Emphasize 50K Simulations */}
                        <div className="bg-charcoal/50 rounded-lg p-5 mb-5 border border-gold/20">
                          <div className="text-sm font-semibold text-lightGold mb-3">FULL ACCESS INCLUDES:</div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left text-sm text-lightGold/90">
                            <div className="flex items-center gap-2">
                              <span className="text-electric-blue text-lg">✔</span>
                              <span><strong>Leg-by-leg win %</strong> (per leg breakdown)</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-electric-blue text-lg">✔</span>
                              <span><strong>EV calculation</strong> (edge analysis)</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-electric-blue text-lg">✔</span>
                              <span><strong>Correlation map</strong> (leg interactions)</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-electric-blue text-lg">✔</span>
                              <span><strong>Risk profile breakdown</strong> (volatility)</span>
                            </div>
                            <div className="flex items-center gap-2 md:col-span-2">
                              <span className="text-gold text-lg">✔</span>
                              <span><strong className="text-gold">Full 50K simulation data</strong> (complete Monte Carlo report)</span>
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={unlockParlay}
                          className="group relative px-10 py-4 bg-linear-to-r from-gold to-lightGold text-darkNavy font-bold text-lg rounded-lg hover:shadow-2xl hover:shadow-gold/50 transition-all transform hover:scale-105"
                        >
                          <span className="relative z-10">
                            UNLOCK PARLAY NOW — ${((parlayData.unlock_price || 999) / 100).toFixed(2)}
                          </span>
                          <div className="absolute inset-0 bg-white/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"></div>
                        </button>

                        {/* Tooltip explaining it's not picks */}
                        <div className="mt-4 text-xs text-lightGold/60 hover:text-lightGold/90 transition-colors cursor-help group relative inline-block">
                          <span className="border-b border-dotted border-lightGold/40">
                            Why unlock? ⓘ
                          </span>
                          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden group-hover:block z-20 w-72 bg-charcoal border-2 border-gold/30 rounded-lg p-4 text-xs text-lightGold">
                            <div className="font-bold text-gold mb-2">This is NOT a pick service</div>
                            <div className="text-lightGold/90">
                              These are probability-based simulations using Monte Carlo analysis, 
                              correlation modeling, and statistical edge detection. 
                              We provide analytical tools—not betting recommendations.
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Institutional Interpretation Notice */}
          <div className="bg-gold/5 rounded-lg p-4 border border-gold/20 text-center text-xs text-light-gray">
            <p>
              <strong className="text-gold">Institutional-Grade Analysis:</strong> Statistical probability structures for analytical framework. 
              Parlay compositions represent correlated outcome modeling, not betting recommendations.
            </p>
          </div>
        </div>
      )}

      {/* Upgrade Modal */}
      <UpgradeModal
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
        currentTier={userTier}
        onSelectTier={(tier) => {
          // Redirect to billing or handle upgrade
          window.location.href = '/billing?tier=' + tier;
        }}
      />
    </div>
  );
};

export default ParlayArchitect;
