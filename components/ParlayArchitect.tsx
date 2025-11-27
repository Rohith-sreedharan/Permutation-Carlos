import React, { useState, useEffect } from 'react';
import api from '../services/api';

interface Leg {
  event: string;
  line: string;
  bet_type: string;
  probability: number;
  confidence: number;
  ev: number;
  volatility?: string;
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
  const [isGenerating, setIsGenerating] = useState(false);
  const [parlayData, setParlayData] = useState<ParlayData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sportOptions = [
    { value: 'basketball_nba', label: 'NBA Basketball' },
    { value: 'americanfootball_nfl', label: 'NFL Football' },
    { value: 'baseball_mlb', label: 'MLB Baseball' },
    { value: 'icehockey_nhl', label: 'NHL Hockey' }
  ];

  const riskProfiles = [
    { value: 'high_confidence', label: 'High Confidence', desc: 'Lower odds, higher win rate' },
    { value: 'balanced', label: 'Balanced', desc: 'Optimal risk/reward mix' },
    { value: 'high_volatility', label: 'High Volatility', desc: 'Moonshot parlays' }
  ];

  const generateParlay = async () => {
    setIsGenerating(true);
    setError(null);
    setParlayData(null);

    try {
      // Get user_id from localStorage if available
      const userId = localStorage.getItem('user_id') || undefined;

      const response = await api.post('http://localhost:8000/api/architect/generate', {
        sport_key: sport,
        leg_count: legCount,
        risk_profile: riskProfile,
        user_id: userId
      });

      // Simulate scanning animation delay
      await new Promise(resolve => setTimeout(resolve, 2000));

      setParlayData(response.data);
    } catch (err: any) {
      // Handle error message from our custom api wrapper or fetch API
      const errorMessage = err.message || err.response?.data?.detail || 'Failed to generate parlay';
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
      const tokenResponse = await api.get(`http://localhost:8000/api/architect/tokens?user_id=${userId}`);
      const { is_elite, tokens_remaining } = tokenResponse.data;

      if (is_elite && tokens_remaining > 0) {
        // Use free Elite token - no payment needed
        const response = await api.post('http://localhost:8000/api/architect/unlock', {
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

        const paymentResponse = await api.post('http://localhost:8000/api/payment/create-micro-charge', {
          product_id: productId,
          user_id: userId,
          parlay_id: parlayData.parlay_id
        });

        // Redirect to Stripe
        window.location.href = paymentResponse.data.checkout_url;
      }
    } catch (err: any) {
      if (err.response?.status === 402) {
        alert(`Payment required: $${(parlayData.unlock_price || 1499) / 100}`);
      } else {
        alert(err.response?.data?.detail || 'Failed to unlock parlay');
      }
    }
  };

  return (
    <div className="min-h-screen bg-darkNavy px-4 py-8">
      {/* Hero Section */}
      <div className="max-w-6xl mx-auto mb-12 text-center">
        <h1 className="text-5xl font-bold text-gold mb-4">
          AI PARLAY ARCHITECT
        </h1>
        <p className="text-lightGold text-lg">
          Simulation-validated probability structures. Not picks. Pure analytics.
        </p>
        <div className="mt-4 inline-block px-6 py-2 bg-deepRed/20 border border-deepRed rounded-lg">
          <span className="text-deepRed font-semibold">PAY-PER-USE ADD-ON</span>
        </div>
      </div>

      {/* Input Wizard */}
      <div className="max-w-3xl mx-auto bg-charcoal rounded-xl p-8 border border-gold/20 mb-8">
        <h2 className="text-2xl font-bold text-gold mb-6">Configure Your Parlay</h2>

        {/* Sport Selection */}
        <div className="mb-6">
          <label className="block text-lightGold mb-2 font-semibold">Sport</label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {sportOptions.map(option => (
              <button
                key={option.value}
                onClick={() => setSport(option.value)}
                className={`px-4 py-3 rounded-lg border-2 transition-all ${
                  sport === option.value
                    ? 'border-gold bg-gold/10 text-gold'
                    : 'border-gold/30 bg-navy/50 text-lightGold hover:border-gold/60'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
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

        {/* Generate Button */}
        <button
          onClick={generateParlay}
          disabled={isGenerating}
          className={`w-full py-4 rounded-lg font-bold text-lg transition-all ${
            isGenerating
              ? 'bg-navy/50 text-lightGold/50 cursor-not-allowed'
              : 'bg-gradient-to-r from-gold to-lightGold text-darkNavy hover:shadow-lg hover:shadow-gold/30'
          }`}
        >
          {isGenerating ? 'SCANNING SIMULATIONS...' : 'GENERATE OPTIMAL PARLAY'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-deepRed/20 border border-deepRed rounded-lg">
            <div className="text-deepRed font-semibold mb-2">⚠️ Generation Failed</div>
            <div className="text-deepRed/90 text-sm mb-2">{error}</div>
            {error.includes('Insufficient') && (
              <div className="text-deepRed/70 text-xs mt-2 pt-2 border-t border-deepRed/30">
                💡 Tip: This occurs when there aren't enough high-confidence simulations available. 
                Try selecting a different sport or reducing the leg count.
              </div>
            )}
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
      {parlayData && !isGenerating && (
        <div className="max-w-4xl mx-auto">
          {/* Overview Card */}
          <div className="bg-gradient-to-br from-charcoal to-navy rounded-xl p-8 border-2 border-gold/30 mb-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-3xl font-bold text-gold">
                {parlayData.is_unlocked ? 'YOUR OPTIMIZED PARLAY' : 'PREVIEW'}
              </h2>
              {!parlayData.is_unlocked && (
                <div className="text-right">
                  <div className="text-sm text-lightGold mb-1">Unlock for</div>
                  <div className="text-2xl font-bold text-gold">
                    ${((parlayData.unlock_price || 1499) / 100).toFixed(2)}
                  </div>
                </div>
              )}
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Parlay Odds</div>
                <div className="text-2xl font-bold text-gold">
                  {parlayData.parlay_odds > 0 ? '+' : ''}{parlayData.parlay_odds}
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Expected Value</div>
                <div className="text-2xl font-bold text-gold">
                  {parlayData.expected_value > 0 ? '+' : ''}{parlayData.expected_value.toFixed(1)}%
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Confidence</div>
                <div className="text-2xl font-bold text-gold">
                  {parlayData.confidence_rating}
                </div>
              </div>
              <div className="bg-navy/50 rounded-lg p-4 border border-gold/20">
                <div className="text-xs text-lightGold/70 mb-1">Win Probability</div>
                <div className="text-2xl font-bold text-gold">
                  {(parlayData.parlay_probability * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Correlation Analysis */}
            {parlayData.is_unlocked && (
              <div className="bg-navy/30 rounded-lg p-4 border border-gold/10 mb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-lightGold mb-1">
                      Correlation Analysis
                    </div>
                    <div className="text-xs text-lightGold/70">
                      {parlayData.correlation_impact}
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-gold">
                    {(parlayData.correlation_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            )}

            {/* Legs */}
            <div className="space-y-3">
              {parlayData.is_unlocked ? (
                // Full data for unlocked
                parlayData.legs.map((leg, idx) => (
                  <div
                    key={idx}
                    className="bg-navy/50 rounded-lg p-4 border border-gold/20"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-bold text-lightGold">
                        Leg {idx + 1}: {leg.event}
                      </div>
                      <div className="text-gold font-mono">
                        {(leg.probability * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <div className="text-lightGold/70">{leg.line}</div>
                      <div className="flex gap-4">
                        <span className="text-lightGold/70">
                          Confidence: <span className="text-gold">{(leg.confidence * 100).toFixed(0)}%</span>
                        </span>
                        <span className="text-lightGold/70">
                          EV: <span className="text-gold">{leg.ev > 0 ? '+' : ''}{leg.ev.toFixed(1)}%</span>
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                // Blurred preview
                <>
                  {parlayData.legs_preview?.map((leg, idx) => (
                    <div
                      key={idx}
                      className="bg-navy/50 rounded-lg p-4 border border-gold/20 relative overflow-hidden"
                    >
                      <div className="blur-sm select-none">
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-bold text-lightGold">
                            Leg {idx + 1}: {leg.event}
                          </div>
                          <div className="text-gold font-mono">{leg.confidence}</div>
                        </div>
                        <div className="text-sm text-lightGold/70">{leg.line}</div>
                      </div>
                      <div className="absolute inset-0 flex items-center justify-center bg-darkNavy/60 backdrop-blur-sm">
                        <div className="text-gold font-bold text-lg">🔒 LOCKED</div>
                      </div>
                    </div>
                  ))}

                  {/* Unlock CTA */}
                  <div className="mt-6 p-6 bg-gradient-to-br from-gold/10 to-deepRed/10 rounded-lg border-2 border-gold/30 text-center">
                    <h3 className="text-xl font-bold text-gold mb-2">
                      Unlock Full Analysis
                    </h3>
                    <p className="text-lightGold/70 mb-4">
                      {parlayData.unlock_message || 'Get complete leg details, correlation analysis, and simulation data'}
                    </p>
                    <button
                      onClick={unlockParlay}
                      className="px-8 py-3 bg-gradient-to-r from-gold to-lightGold text-darkNavy font-bold rounded-lg hover:shadow-lg hover:shadow-gold/30 transition-all"
                    >
                      UNLOCK FOR ${((parlayData.unlock_price || 1499) / 100).toFixed(2)}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Compliance Disclaimer */}
          <div className="bg-navy/30 rounded-lg p-4 border border-gold/10 text-center text-xs text-lightGold/70">
            <p>
              <strong className="text-gold">Compliance Notice:</strong> We are not selling picks. 
              This is a simulation-validated probability structure for analytical purposes only. 
              Always gamble responsibly.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ParlayArchitect;
