/**
 * GameDetail Component - Elite Sports Intelligence Dashboard
 * 
 * RECENT CRITICAL FIXES (Dec 2025):
 * --------------------------------
 * 1. ✅ Color-coded Key Drivers (🔴 Injuries, 🔵 Tempo, 🟡 Simulation Depth)
 * 2. ✅ Misprice Status now shows context: "(Total mispriced by X pts)"
 * 3. ✅ Confidence Score includes tier scale explanation (S-Tier: 90-100, A-Tier: 85-89, etc.)
 * 4. ✅ Volatility card shows actionable context ("Expect large scoring swings. Avoid heavy exposure.")
 * 5. ✅ Sim Count now displays correct tier alignment ("50K Elite tier analysis" vs "10K Starter tier")
 * 6. ✅ Added tier upgrade messaging when viewing higher-tier simulations
 * 7. ✅ Sticky tab navigation with glowing active state
 * 8. ✅ Win Probability logic documented - should align with spread edge (backend may need adjustment)
 * 
 * KNOWN BACKEND ISSUE TO FIX:
 * ---------------------------
 * • Win Probability inconsistency: +9.3 point edge should correlate to ~65-75% win probability
 *   Current: Shows 40.6% (underdog) despite having +9.3 edge (favorite)
 *   Root Cause: Backend simulation.win_probability may be pulling from market odds instead of sim distribution
 *   Fix Required: Ensure win_probability = P(model_score > opponent_score) from Monte Carlo output
 */

import React, { useState, useEffect } from 'react';
import { fetchSimulation, fetchEventsFromDB } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import SocialMetaTags from './SocialMetaTags';
import FirstHalfAnalysis from './FirstHalfAnalysis';
import SimulationBadge from './SimulationBadge';
import ConfidenceGauge from './ConfidenceGauge';
import UpgradePrompt from './UpgradePrompt';
import { getUserTierInfo, type TierName } from '../utils/tierConfig';
import { getConfidenceTier, getConfidenceGlow, getConfidenceBadgeStyle } from '../utils/confidenceTiers';
import { getSportLabels } from '../utils/sportLabels';
import { validateEdge, getImpliedProbability, explainEdgeSource, type EdgeValidationInput } from '../utils/edgeValidation';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';
import type { Event as EventType, MonteCarloSimulation, EventWithPrediction } from '../types';

interface GameDetailProps {
  gameId: string;
  onBack: () => void;
}

const GameDetail: React.FC<GameDetailProps> = ({ gameId, onBack }) => {
  const [simulation, setSimulation] = useState<MonteCarloSimulation | null>(null);
  const [firstHalfSimulation, setFirstHalfSimulation] = useState<any | null>(null);
  const [event, setEvent] = useState<EventType | null>(null);
  const [loading, setLoading] = useState(true);
  const [firstHalfLoading, setFirstHalfLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'distribution' | 'injuries' | 'props' | 'movement' | 'pulse' | 'firsthalf'>('distribution');
  const [propsSortBy, setPropsSortBy] = useState('ev');
  const [lineMovementData, setLineMovementData] = useState<Array<{ time: string; odds: number; fairValue: number }>>([]);
  const [shareSuccess, setShareSuccess] = useState(false);
  const [followSuccess, setFollowSuccess] = useState(false);
  const [isFollowing, setIsFollowing] = useState(false);
  
  // PHASE 18: Confidence tooltip and banners
  const [confidenceTooltip, setConfidenceTooltip] = useState<{
    score: number;
    label: string;
    banner_type: 'success' | 'warning' | 'info';
    banner_message: string;
    tooltip: string;
  } | null>(null);
  
  // User tier information for upgrade prompts
  const userTier = simulation?.metadata?.user_tier || 'free';
  const currentIterations = simulation?.iterations || simulation?.metadata?.iterations_run || 10000;

  useEffect(() => {
    loadGameData();
    loadFirstHalfData();
    generateLineMovement();
  }, [gameId]);
  
  // PHASE 18: Load confidence UI elements
  useEffect(() => {
    if (simulation) {
      fetchConfidenceTooltip();
    }
  }, [simulation]);

  const fetchConfidenceTooltip = async () => {
    if (!simulation) return;
    
    try {
      const confidenceScore = Math.round((simulation.confidence_score || 0.65) * 100);
      const volatilityIndex = typeof simulation.volatility_index === 'string' ? 
        simulation.volatility_index.toUpperCase() : 
        simulation.volatility_score || 'MODERATE';
      const simCount = simulation.iterations || 50000;
      
      const response = await fetch(
        `http://localhost:8000/api/analytics/confidence-tooltip?confidence_score=${confidenceScore}&volatility=${volatilityIndex}&sim_count=${simCount}`
      );
      
      if (response.ok) {
        const data = await response.json();
        setConfidenceTooltip(data);
      }
    } catch (err) {
      console.error('Failed to fetch confidence tooltip:', err);
    }
  };

  const loadGameData = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      
      // Fetch simulation data and ALL events from database (all sports)
      const [simData, eventsData] = await Promise.all([
        fetchSimulation(gameId),
        fetchEventsFromDB(undefined, undefined, false, 500) // No sport filter, get all upcoming
      ]);

      console.log('[GameDetail] Fetched events:', eventsData.length);
      console.log('[GameDetail] Looking for gameId:', gameId);

      setSimulation(simData);
      const gameEvent = eventsData.find((e: EventType) => e.id === gameId);
      
      console.log('[GameDetail] Found event:', gameEvent);
      
      setEvent(gameEvent || null);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load game details');
      console.error('[GameDetail] Error:', err);
    } finally {
      setLoading(false);
    }
  };

  // PHASE 15: Load First Half simulation data
  const loadFirstHalfData = async () => {
    if (!gameId) return;

    try {
      setFirstHalfLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch(`http://localhost:8000/api/simulations/${gameId}/period/1H`, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setFirstHalfSimulation(data);
      } else {
        console.warn('First half simulation not available');
      }
    } catch (err) {
      console.error('Failed to load first half data:', err);
    } finally {
      setFirstHalfLoading(false);
    }
  };

  // Generate 24-hour line movement data (Market Agent output simulation)
  const generateLineMovement = () => {
    const now = Date.now();
    const data = [];
    for (let i = 24; i >= 0; i--) {
      const time = new Date(now - i * 60 * 60 * 1000);
      const odds = 1.85 + (Math.random() - 0.5) * 0.15; // Market odds fluctuation
      const fairValue = 1.90 + (Math.random() - 0.5) * 0.05; // Fair value (more stable)
      data.push({
        time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        odds: parseFloat(odds.toFixed(2)),
        fairValue: parseFloat(fairValue.toFixed(2))
      });
    }
    setLineMovementData(data);
  };

  // Share Game Analysis (Blueprint Page 64: Creator Distribution Moat)
  const handleShare = async () => {
    if (!simulation || !event) return;

    const winProb = ((simulation.team_a_win_probability || simulation.win_probability || 0.5) * 100).toFixed(1);
    const volatility = typeof simulation.volatility_index === 'string' ? simulation.volatility_index.toUpperCase() : 
                      simulation.volatility_score || 'MODERATE';
    // FIX: Convert decimal confidence to percentage BEFORE rounding
    const confidence = Math.round((simulation.confidence_score || 0.65) * 100);

    const shareText = `🏀 ${event.away_team} @ ${event.home_team}\n\n📊 AI Model Analysis (${(simulation.iterations || 10000).toLocaleString()} simulations):\n• Win Probability: ${winProb}%\n• Volatility: ${volatility}\n• Confidence Score: ${confidence}/100\n\n🚀 Powered by #BeatVegas Monte Carlo AI\nbeatvegas.com/game/${gameId}`;

    try {
      await navigator.clipboard.writeText(shareText);
      setShareSuccess(true);
      setTimeout(() => setShareSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      alert('Failed to copy. Please try again.');
    }
  };

  // Follow Forecast - Track in Decision Command Center
  const handleFollowForecast = async () => {
    if (!simulation || !event || isFollowing) return;

    setIsFollowing(true);

    try {
      const token = localStorage.getItem('authToken');
      const response = await fetch('http://localhost:8000/api/user/follow-forecast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          event_id: gameId,
          pick_id: simulation.simulation_id,
          confidence_score: simulation.confidence_score || 0.65,
          expected_value: 0.05  // Default EV estimate
        })
      });

      if (response.ok) {
        setFollowSuccess(true);
        setTimeout(() => setFollowSuccess(false), 3000);
      } else {
        console.error('Failed to follow forecast');
      }
    } catch (err) {
      console.error('Error following forecast:', err);
    } finally {
      setIsFollowing(false);
    }
  };

  const getVolatilityColor = (volatility: string | number) => {
    const vol = typeof volatility === 'string' ? volatility.toLowerCase() : 
                volatility < 0.3 ? 'stable' : volatility > 0.7 ? 'high' : 'moderate';
    switch (vol) {
      case 'stable': case 'low': return 'text-neon-green';
      case 'moderate': case 'medium': return 'text-yellow-500';
      case 'high': return 'text-bold-red';
      default: return 'text-light-gray';
    }
  };

  const getVolatilityIcon = (volatility: string | number) => {
    const vol = typeof volatility === 'string' ? volatility.toLowerCase() : 
                volatility < 0.3 ? 'stable' : volatility > 0.7 ? 'high' : 'moderate';
    switch (vol) {
      case 'stable': case 'low': return '📊';
      case 'moderate': case 'medium': return '⚡';
      case 'high': return '🌪️';
      default: return '📈';
    }
  };

  const getVolatilityLabel = (volatility: string | number): string => {
    if (typeof volatility === 'string') return volatility.toUpperCase();
    if (volatility < 0.3) return 'STABLE';
    if (volatility > 0.7) return 'HIGH';
    return 'MODERATE';
  };

  // Render Confidence Gauge (0-100 scale)
  const renderConfidenceGauge = (score: number) => {
    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;
    const color = score >= 75 ? '#7CFC00' : score >= 50 ? '#FFD700' : '#FF4444';

    return (
      <div className="relative inline-flex items-center justify-center">
        <svg className="transform -rotate-90" width="160" height="160">
          <circle
            cx="80"
            cy="80"
            r={radius}
            stroke="#1e293b"
            strokeWidth="12"
            fill="none"
          />
          <circle
            cx="80"
            cy="80"
            r={radius}
            stroke={color}
            strokeWidth="12"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-1000"
          />
        </svg>
        <div className="absolute text-center">
          <div className="text-4xl font-bold" style={{ color }}>{score}</div>
          <div className="text-sm text-light-gray">CONFIDENCE</div>
        </div>
      </div>
    );
  };

  if (loading) return <LoadingSpinner />;
  if (error) return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <div className="text-center">
        <div className="text-bold-red text-xl mb-4">{error}</div>
        <button
          onClick={onBack}
          className="bg-gold text-white px-6 py-2 rounded-lg hover:opacity-80"
        >
          ← Back to Dashboard
        </button>
      </div>
    </div>
  );
  if (!simulation || !event) return <div className="text-center text-white p-8">Game not found</div>;

  // Prepare chart data - handle both array and object formats
  const spreadDistArray = Array.isArray(simulation.spread_distribution) 
    ? simulation.spread_distribution 
    : simulation.spread_distribution 
      ? Object.entries(simulation.spread_distribution).map(([margin, prob]) => ({
          margin: parseFloat(margin),
          probability: prob as number
        }))
      : [];
  
  // FIX: Show centered distribution around 0 (-20 to +20) instead of last 30 margins
  const scoreDistData = spreadDistArray
    .filter(d => d.margin >= -20 && d.margin <= 20)  // Center around even matchup
    .sort((a, b) => a.margin - b.margin)  // Sort by margin ascending
    .map(d => ({
      margin: d.margin,
      probability: (d.probability * 100).toFixed(1)
    }));

  // Debug logging
  console.log('🎯 GameDetail Debug:', {
    has_simulation: !!simulation,
    user_tier: simulation?.metadata?.user_tier,
    iterations: simulation?.iterations,
    has_spread_dist: !!simulation?.spread_distribution,
    spread_dist_type: Array.isArray(simulation?.spread_distribution) ? 'array' : typeof simulation?.spread_distribution,
    spread_dist_length: spreadDistArray.length,
    scoreDistData_length: scoreDistData.length,
    first_5_items: scoreDistData.slice(0, 5)
  });
  
  if (scoreDistData.length === 0) {
    console.warn('⚠️ No distribution data:', {
      spread_distribution: simulation.spread_distribution,
      spreadDistArray,
      simulation_id: simulation.simulation_id
    });
  }

  const winProb = simulation.win_probability ?? simulation.team_a_win_probability ?? 0.5;
  
  // Edge Validation: Prepare inputs for 7-rule validation
  const impliedProb = simulation.market_context?.spread 
    ? getImpliedProbability(simulation.market_context.spread)
    : 0.5;
  
  const edgeValidationInput: EdgeValidationInput = {
    win_probability: winProb,
    implied_probability: impliedProb,
    confidence: (simulation.outcome?.confidence || 0.65) * 100,
    volatility: String(simulation.volatility_index || 'moderate'),
    sim_count: simulation.iterations || 10000,
    expected_value: simulation.outcome?.expected_value_percent || 0,
    distribution_favor: winProb > 0.5 ? ((winProb - 0.5) * 2) * 100 : ((0.5 - winProb) * 2) * 100,
    injury_impact: simulation.injury_impact?.reduce((sum: number, inj: any) => sum + Math.abs(inj.offensive_impact || 0) + Math.abs(inj.defensive_impact || 0), 0) || 0,
    model_spread: Math.abs(simulation.avg_margin || 0) // Model's predicted point spread
  };
  
  const edgeValidation = validateEdge(edgeValidationInput);
  const edgeExplanation = explainEdgeSource(edgeValidation, {
    pace_factor: simulation.pace_factor,
    injury_impact: simulation.injury_impact?.reduce((sum: number, inj: any) => sum + Math.abs(inj.offensive_impact || 0) + Math.abs(inj.defensive_impact || 0), 0) || 0,
    rest_advantage: 0,
    matchup_rating: winProb,
    market_inefficiency: Math.abs((simulation.projected_score || 220) - (simulation.vegas_line || 220))
  });
  
  // CLV Prediction: Forecast closing line movement
  const calculateCLV = () => {
    const sharpAction = edgeValidation.classification === 'EDGE' ? 'heavy' : 'moderate';
    const edgeStrength = Math.abs(winProb - impliedProb);
    const predictedMovement = sharpAction === 'heavy' 
      ? edgeStrength * 1.5 : edgeStrength * 0.5;
    
    return {
      predicted_closing_line: simulation.market_context?.spread 
        ? (simulation.market_context.spread + (winProb > impliedProb ? predictedMovement : -predictedMovement))
        : 0,
      clv_value: predictedMovement,
      confidence: edgeValidation.classification === 'EDGE' ? 'High' : 'Medium',
      reasoning: sharpAction === 'heavy' 
        ? 'Strong model edge suggests sharp action will move line toward simulation projection'
        : 'Moderate edge may see gradual line adjustment as market discovers value'
    };
  };
  
  const clvPrediction = calculateCLV();
  
  // NOTE: Win probability should reflect simulation's predicted outcome distribution
  // If there's a mismatch between winProb and spread edge, the backend simulation may need adjustment
  // Example: +9.3 point edge should correlate to ~65-75% win probability depending on variance
  const varianceValue = simulation.variance ?? 100;
  const volatilityIndex = simulation.volatility_index ?? 'moderate';

  // Calculate confidence intervals if not provided
  const confidenceIntervals = simulation.confidence_intervals ?? {
    ci_68: [simulation.avg_margin - 5, simulation.avg_margin + 5] as [number, number],
    ci_95: [simulation.avg_margin - 10, simulation.avg_margin + 10] as [number, number],
    ci_99: [simulation.avg_margin - 15, simulation.avg_margin + 15] as [number, number]
  };

  // Dynamic community pulse based on simulation probabilities
  const homeWinProb = (simulation.team_a_win_probability || simulation.win_probability || 0.5) * 100;
  const awayWinProb = 100 - homeWinProb;
  
  // Get Over/Under from simulation (use actual data from backend)
  const totalScore = simulation.avg_total_score || simulation.avg_total || 220;
  const overProb = simulation.over_probability ? simulation.over_probability * 100 : 
    (totalScore > 215 ? Math.min(65, 45 + (totalScore - 215) * 2) : Math.max(35, 45 - (215 - totalScore) * 2));
  const underProb = simulation.under_probability ? simulation.under_probability * 100 : (100 - overProb);
  const totalLine = simulation.market_context?.total_line || Math.round(totalScore * 2) / 2;
  
  // 🔍 DEBUG: Log team perspective for win probability diagnosis
  if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    console.log('🔍 Win Probability Debug:', {
      event_id: event.id,
      home_team: event.home_team,
      away_team: event.away_team,
      simulation_team_a: simulation.team_a,
      simulation_team_b: simulation.team_b,
      team_a_win_prob: simulation.team_a_win_probability,
      team_b_win_prob: simulation.team_b_win_probability,
      win_probability: simulation.win_probability,
      displayed_winProb: winProb,
      avg_margin: simulation.avg_margin,
      spread_edge: Math.abs((simulation.projected_score || totalLine) - (simulation.vegas_line || totalLine))
    });
  }
  
  const communityPulseData = [
    { category: 'Home ML', picks: Math.round(homeWinProb) },
    { category: 'Away ML', picks: Math.round(awayWinProb) },
    { category: 'Over', picks: Math.round(overProb) },
    { category: 'Under', picks: Math.round(underProb) }
  ];

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      {/* Dynamic SEO/Meta Tags for Social Sharing */}
      <SocialMetaTags 
        event={event && simulation ? {
          ...event,
          prediction: {
            event_id: event.id,
            recommended_bet: simulation.outcome?.recommended_bet || null,
            confidence: simulation.outcome?.confidence || 0,
            ev_percent: simulation.outcome?.expected_value_percent || 0,
            volatility: simulation.volatility || 'MODERATE',
            outcome_probabilities: {},
            sharp_money_indicator: 0,
            correlation_score: 0
          }
        } as EventWithPrediction : undefined}
        pageType="gameDetail"
      />

      {/* Back Navigation */}
      <button
        onClick={onBack}
        className="text-gold hover:text-white mb-4 flex items-center space-x-2 transition"
      >
        <span>←</span>
        <span>Back to Dashboard</span>
      </button>

      {/* Game Header */}
      <div className="bg-gradient-to-b from-navy/30 via-transparent to-transparent pb-4 -mb-4 rounded-t-xl">
      <PageHeader title={`${event.away_team} @ ${event.home_team}`}>
        <div className="flex items-center space-x-4">
          <span className="bg-gold/20 text-gold text-xs font-bold px-3 py-1 rounded-full uppercase">
            {event.sport_key}
          </span>
          <span className="text-light-gray text-sm">
            {new Date(event.commence_time).toLocaleString()}
          </span>
          {/* Follow Forecast Button */}
          <button
            onClick={handleFollowForecast}
            disabled={isFollowing}
            className={`${
              followSuccess ? 'bg-neon-green' : 'bg-gradient-to-r from-gold to-purple-600'
            } text-white font-bold px-4 py-2 rounded-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <span>{followSuccess ? '✓' : '⭐'}</span>
            <span>{followSuccess ? 'Following' : 'Follow'}</span>
          </button>
          {/* Share Button (Blueprint Page 64) */}
          <button
            onClick={handleShare}
            className="bg-gradient-to-r from-purple-600 to-pink-600 text-white font-bold px-4 py-2 rounded-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center space-x-2"
          >
            <span>📤</span>
            <span>Share</span>
            {shareSuccess && <span className="text-neon-green">✓</span>}
          </button>
        </div>
      </PageHeader>

      {followSuccess && (
        <div className="mb-4 bg-gold/20 border border-gold rounded-lg p-3 text-center text-gold text-sm animate-pulse">
          ⭐ Forecast added to your Decision Command Center!
        </div>
      )}

      </div>
      {/* END: Header gradient wrapper */}

      {shareSuccess && (
        <div className="mb-4 bg-neon-green/20 border border-neon-green rounded-lg p-3 text-center text-neon-green text-sm animate-pulse">
          ✓ Game analysis copied to clipboard! Share on social media with #BeatVegas
        </div>
      )}

      {/* Simulation Power Badge - MOVED TO TOP */}
      <div className="mb-3 animate-fade-in">
        <SimulationBadge 
          tier={(simulation?.metadata?.user_tier || 'free') as TierName} 
          simulationCount={simulation?.metadata?.sim_count_used || simulation?.iterations || 100000}
          variance={simulation?.metadata?.variance || simulation?.variance}
          ci95={simulation?.metadata?.ci_95 || simulation?.confidence_intervals?.ci_95}
          showUpgradeHint={simulation?.metadata?.user_tier === 'free'}
        />
      </div>

      {/* KEY DRIVERS BOX - Critical Context */}
      {simulation && (
        <div className="mb-6 bg-gradient-to-br from-purple-900/20 to-blue-900/20 border border-purple-500/30 rounded-xl p-5">
          <div className="flex items-start">
            <span className="text-3xl mr-3">🔑</span>
            <div className="flex-1">
              <h3 className="text-purple-300 font-bold text-lg mb-2">Key Drivers</h3>
              <div className="text-light-gray text-sm space-y-1">
                {simulation.injury_impact && simulation.injury_impact.length > 0 && (
                  <div>• 🔴 <span className="text-bold-red font-semibold">Injuries:</span> {simulation.injury_impact.length} players impacted ({simulation.injury_impact.reduce((sum: number, inj: any) => sum + Math.abs(inj.impact_points), 0).toFixed(1)} pts total effect)</div>
                )}
                {simulation.pace_factor && simulation.pace_factor !== 1.0 && (
                  <div>• 🔵 <span className="text-electric-blue font-semibold">Tempo:</span> {simulation.pace_factor > 1 ? 'Fast-paced' : 'Slow-paced'} game expected ({((simulation.pace_factor - 1) * 100).toFixed(1)}% {simulation.pace_factor > 1 ? 'above' : 'below'} average)</div>
                )}
                {simulation.outcome?.confidence && (
                  <div>• 🟡 <span className="text-gold font-semibold">Stability:</span> {getConfidenceTier((simulation.outcome.confidence || 0.65) * 100).label} ({((simulation.outcome.confidence || 0.65) * 100).toFixed(0)}% simulation convergence)</div>
                )}
                {simulation.metadata?.iterations_run && (
                  <div>• 🧪 <span className="text-neon-green font-semibold">Simulation Depth:</span> {(simulation.metadata.iterations_run / 1000).toFixed(0)}K {simulation.metadata.user_tier === 'elite' ? 'Elite' : simulation.metadata.user_tier === 'pro' ? 'Pro' : 'Starter'} tier analysis</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODEL OUTPUT SUMMARY - Neutral Statistical Display */}
      {simulation.outcome && (
        <div 
          className="mb-6 bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border-2 animate-slide-up relative overflow-hidden"
          style={{
            borderColor: getConfidenceTier((simulation.outcome?.confidence || 0.65) * 100).color,
            boxShadow: getConfidenceGlow((simulation.outcome?.confidence || 0.65) * 100)
          }}
        >
          {/* Subtle tier-colored gradient background */}
          <div 
            className="absolute inset-0 opacity-5"
            style={{
              background: `linear-gradient(135deg, ${getConfidenceTier((simulation.outcome?.confidence || 0.65) * 100).color} 0%, transparent 50%)`
            }}
          />
          
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex-1">
              <div className="text-xs text-light-gray uppercase mb-1">
                📊 MODEL OUTPUT SUMMARY
              </div>
              <div className="text-2xl font-bold text-white mb-2 font-teko">
                Statistical Analysis Results
              </div>
              
              {/* Model Projection vs Book Line Comparison */}
              <div className="text-sm text-light-gray space-y-1">
                <div>
                  <span className="text-gold">Model Projection:</span> {simulation.projected_score || totalLine.toFixed(1)} 
                </div>
                <div>
                  <span className="text-electric-blue">Book Line:</span> {simulation.vegas_line || totalLine.toFixed(1)}
                </div>
                <div>
                  <span className="text-light-gray">Variance Gap:</span> {Math.abs((simulation.projected_score || totalLine) - (simulation.vegas_line || totalLine)).toFixed(1)} points
                </div>
              </div>
              
              {/* Model Variance Gap (not EV) */}
              <div className="mt-3 text-xs bg-navy/50 rounded px-3 py-2">
                <div className="text-light-gray mb-1">Model Variance Gap:</div>
                <span className="font-mono text-electric-blue">
                  {Math.abs((simulation.outcome?.expected_value_percent || 0)).toFixed(2)}%
                </span>
                <div className="text-xs text-light-gray/60 mt-1">
                  (Difference between model projection & book line. Not betting value.)
                </div>
              </div>
            </div>
            
            {/* Simulation Stability Gauge */}
            <div className="ml-6">
              <ConfidenceGauge 
                confidence={(simulation.outcome?.confidence || 0.65) * 100}
                size="md"
                animated={true}
              />
            </div>
          </div>
          
          {/* Upgrade Prompt */}
          <div className="mt-4">
            <UpgradePrompt variant="confidence" currentTier={userTier} currentIterations={currentIterations} />
          </div>
          
          {/* Simulation Power Tier Badge */}
          <div className="mt-4 pt-4 border-t border-white/10">
            <div 
              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold"
              style={getConfidenceBadgeStyle((simulation.outcome?.confidence || 0.65) * 100)}
            >
              {getConfidenceTier((simulation.outcome?.confidence || 0.65) * 100).label}
            </div>
          </div>
        </div>
      )}

      {/* HERO SECTION: BeatVegas Edge Detection */}
      {simulation && (
        <div className="mb-6 p-6 bg-gradient-to-br from-purple-900/20 via-navy/40 to-electric-blue/20 rounded-xl border border-purple-500/30 relative overflow-hidden shadow-xl shadow-purple-500/10">
          <div className="absolute top-0 right-0 w-32 h-32 bg-electric-blue/10 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-8 -left-8 w-24 h-24 bg-gold/5 rounded-full blur-2xl"></div>
          <div className="relative z-10">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <div className="text-3xl">{edgeValidation.classification === 'EDGE' ? '🎯' : edgeValidation.classification === 'LEAN' ? '⚡' : '✅'}</div>
                  <div>
                    <h3 className={`text-2xl font-bold font-teko leading-none ${
                      edgeValidation.classification === 'EDGE' ? 'text-neon-green' :
                      edgeValidation.classification === 'LEAN' ? 'text-gold' :
                      'text-electric-blue'
                    }`}>
                      {edgeValidation.classification === 'EDGE' ? 'BEATVEGAS EDGE DETECTED' :
                       edgeValidation.classification === 'LEAN' ? 'MODERATE LEAN IDENTIFIED' :
                       'MARKET ALIGNED - NO EDGE'}
                    </h3>
                    <p className="text-xs text-light-gray mt-1">
                      {edgeValidation.classification === 'EDGE' ? 'High-Conviction Quantitative Signal' :
                       edgeValidation.classification === 'LEAN' ? 'Soft Edge - Proceed with Caution' :
                       'Model-Market Consensus Detected'}
                    </p>
                  </div>
                </div>
                
                <div className="grid grid-cols-4 gap-4 mt-4">
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">Edge Classification</div>
                    <div className={`text-3xl font-black font-teko ${
                      edgeValidation.classification === 'EDGE' ? 'text-neon-green' :
                      edgeValidation.classification === 'LEAN' ? 'text-gold' :
                      'text-electric-blue'
                    }`}>
                      {edgeValidation.classification}
                    </div>
                    <div className={`text-xs font-semibold mt-1 ${
                      edgeValidation.classification === 'LEAN' ? 'text-gold/80' : 'text-light-gray/60'
                    }`}>
                      {edgeValidation.classification === 'LEAN' ? 'Soft edge — proceed cautious' : `${edgeValidation.passed_rules}/${edgeValidation.total_rules} rules passed`}
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20 relative group">
                    <div className="text-xs text-light-gray mb-1">Model Spread</div>
                    <div className="text-2xl font-bold text-electric-blue font-teko">
                      {((simulation.team_a_win_probability || simulation.win_probability || 0.5) > 0.5 ? '-' : '+')}{Math.abs((simulation.projected_score || 220) - (simulation.vegas_line || 220)).toFixed(1)}
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">vs market</div>
                    {/* Critical Disclaimer Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-56 p-3 bg-bold-red/95 border-2 border-bold-red rounded-lg shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10">
                      <p className="text-xs text-white font-semibold leading-relaxed">
                        ⚠️ This is model vs book deviation, NOT a betting pick. Do not bet based on this number alone.
                      </p>
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">CLV Prediction</div>
                    <div className="text-2xl font-bold text-neon-green font-teko">
                      {clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)}%
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">
                      {clvPrediction.confidence} confidence
                    </div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-gold/20">
                    <div className="text-xs text-light-gray mb-1">Total Deviation</div>
                    <div className="text-2xl font-bold text-electric-blue font-teko">
                      +{Math.abs((simulation.projected_score || 220) - (simulation.vegas_line || 220)).toFixed(1)} pts
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">model vs book</div>
                  </div>
                </div>
                
                {/* Edge Validation Warnings */}
                {edgeValidation.failed_rules.length > 0 && (
                  <div className="mt-3 p-3 bg-bold-red/10 border border-bold-red/30 rounded-lg">
                    <div className="text-xs font-bold text-bold-red mb-2">⚠️ Edge Quality Warnings:</div>
                    <ul className="text-xs text-light-gray space-y-1">
                      {edgeValidation.failed_rules.map((rule, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-bold-red">•</span>
                          <span>{rule}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                <details className="mt-4 cursor-pointer group">
                  <summary className="text-xs font-bold text-white uppercase tracking-wide list-none flex items-center gap-2 hover:text-gold transition">
                    <span className="transform group-open:rotate-90 transition-transform">▶</span>
                    Edge Summary
                  </summary>
                  <div className="mt-3 text-xs text-light-gray/80 leading-relaxed pl-4 border-l-2 border-gold/30">
                    {edgeValidation.summary}
                    <br /><br />
                    Expected line movement: <strong className="text-gold">{clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)} points</strong> by kickoff
                  </div>
                </details>
                
                {/* CLV Prediction Details */}
                <div className="mt-3 p-3 bg-navy/30 rounded-lg border border-electric-blue/20">
                  <div className="text-xs font-bold text-electric-blue mb-2">📈 Closing Line Value (CLV) Forecast</div>
                  <div className="text-xs text-light-gray leading-relaxed">
                    {clvPrediction.reasoning}
                  </div>
                  <div className="text-xs text-gold mt-2">
                    Expected line movement: <strong>{clvPrediction.clv_value > 0 ? '+' : ''}{clvPrediction.clv_value.toFixed(1)} points</strong> by kickoff
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Sharp Analysis - Model vs Market */}
      {simulation?.sharp_analysis && (simulation.sharp_analysis.total?.has_edge || simulation.sharp_analysis.spread?.has_edge) && (
        <div className="mb-6 p-6 bg-gradient-to-br from-purple-900/30 to-blue-900/30 rounded-xl border-2 border-purple-500/50 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="text-4xl">🎯</div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-purple-300 mb-2 font-teko">SHARP SIDE DETECTED</h3>
              
              {/* CRITICAL DISCLAIMER */}
              <div className="mb-4 p-3 bg-bold-red/20 border-2 border-bold-red/60 rounded-lg">
                <p className="text-xs text-bold-red font-bold flex items-center gap-2">
                  <span className="text-base">⚠️</span>
                  <span>Sharp Side = model mispricing detection, NOT a betting recommendation. This platform provides statistical analysis only.</span>
                </p>
              </div>
              

              {simulation.sharp_analysis.total?.has_edge && (
                <div className="mb-4 p-4 bg-charcoal/50 rounded-lg border border-purple-500/30">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                        simulation.sharp_analysis.total.edge_grade === 'S' ? 'bg-purple-600 text-white' :
                        simulation.sharp_analysis.total.edge_grade === 'A' ? 'bg-green-600 text-white' :
                        simulation.sharp_analysis.total.edge_grade === 'B' ? 'bg-blue-600 text-white' :
                        'bg-yellow-600 text-black'
                      }`}>
                        {simulation.sharp_analysis.total.edge_grade} GRADE
                      </div>
                      <div className="text-lg font-bold text-white">
                        {simulation.sharp_analysis.total.sharp_side_display}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-400">Edge</div>
                      <div className="text-lg font-bold text-purple-300">
                        {simulation.sharp_analysis.total.edge_points?.toFixed(1)} pts
                      </div>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">Vegas Line</div>
                      <div className="text-base font-bold text-white">
                        O/U {simulation.sharp_analysis.total.vegas_total}
                      </div>
                    </div>
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">BeatVegas Model</div>
                      <div className="text-base font-bold text-purple-300">
                        {simulation.sharp_analysis.total.model_total?.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  
                  {/* Edge Reasoning */}
                  {simulation.sharp_analysis.total.edge_reasoning && (
                    <div className="mt-4 p-4 bg-purple-900/20 rounded-lg border-l-4 border-purple-500">
                      <div className="text-xs font-bold text-purple-300 mb-2">
                        🔍 Why Our Model Found Edge on {simulation.sharp_analysis.total.edge_direction} {simulation.sharp_analysis.total.vegas_total}:
                      </div>
                      
                      <div className="text-sm text-gray-300 mb-3 leading-relaxed">
                        {simulation.sharp_analysis.total.edge_reasoning.model_reasoning}
                      </div>
                      
                      <div className="text-xs font-bold text-purple-300 mb-2">Primary Factor:</div>
                      <div className="text-sm text-white mb-3">
                        {simulation.sharp_analysis.total.edge_reasoning.primary_factor}
                      </div>
                      
                      {simulation.sharp_analysis.total.edge_reasoning.contributing_factors?.length > 0 && (
                        <>
                          <div className="text-xs font-bold text-purple-300 mb-2">Contributing Factors:</div>
                          <div className="space-y-1 mb-3">
                            {simulation.sharp_analysis.total.edge_reasoning.contributing_factors.map((factor, idx) => (
                              <div key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                                <span className="text-purple-400">•</span>
                                <span>{factor}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                      
                      <div className="text-xs text-gray-400 italic mt-3 p-2 bg-charcoal/50 rounded">
                        {simulation.sharp_analysis.total.edge_reasoning.market_positioning}
                      </div>
                      
                      {simulation.sharp_analysis.total.edge_reasoning.contrarian_indicator && (
                        <div className="mt-3 flex items-center gap-2 text-xs font-bold text-yellow-400">
                          <span>⚠️</span>
                          <span>CONTRARIAN POSITION - Model diverges significantly from market consensus</span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-3 text-xs text-gray-500 italic">
                    {simulation.sharp_analysis.disclaimer}
                  </div>
                </div>
              )}
              
              {/* Spread Analysis (if exists) */}
              {simulation.sharp_analysis.spread?.has_edge && (
                <div className="p-4 bg-charcoal/50 rounded-lg border border-purple-500/30">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                      simulation.sharp_analysis.spread.edge_grade === 'S' ? 'bg-purple-600 text-white' :
                      simulation.sharp_analysis.spread.edge_grade === 'A' ? 'bg-green-600 text-white' :
                      'bg-blue-600 text-white'
                    }`}>
                      {simulation.sharp_analysis.spread.edge_grade} GRADE
                    </div>
                    <div className="text-lg font-bold text-white">
                      {simulation.sharp_analysis.spread.sharp_side_display}
                    </div>
                    <div className="text-sm text-purple-300">
                      ({simulation.sharp_analysis.spread.edge_points?.toFixed(1)} pt edge)
                    </div>
                  </div>
                  <div className="text-sm text-gray-300 mt-2">
                    {simulation.sharp_analysis.spread.sharp_side_reason}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Why This Edge Exists - Explanation Panel */}
      {edgeValidation.classification !== 'NEUTRAL' && (
        <div className="mb-6 p-5 bg-gradient-to-r from-navy/40 to-charcoal/60 rounded-xl border border-gold/30 shadow-lg">
          <div className="flex items-start gap-3">
            <div className="text-2xl">💡</div>
            <div className="flex-1">
              <h4 className="text-lg font-bold text-white mb-2 font-teko">Why This Edge Exists</h4>
              <div className="text-xs text-gold/70 mb-2 uppercase tracking-wide">
                {simulation?.sharp_analysis?.total?.has_edge && simulation?.sharp_analysis?.spread?.has_edge ? 'Both Spread & Total' :
                 simulation?.sharp_analysis?.total?.has_edge ? 'Total Market Only' :
                 simulation?.sharp_analysis?.spread?.has_edge ? 'Spread Market Only' : 'Global Edge Detection'}
              </div>
              <div className="text-sm text-light-gray leading-relaxed">
                {edgeExplanation.explanation}
              </div>
              
              {/* Edge Factors Breakdown */}
              {edgeExplanation.factors.length > 0 && (
                <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                  {edgeExplanation.factors.map((factor, idx) => (
                    <div key={idx} className="bg-charcoal/50 p-2 rounded border border-gold/10">
                      <div className="text-xs text-gold font-bold">{factor.type}</div>
                      <div className="text-xs text-light-gray mt-1">{factor.description}</div>
                      <div className={`text-xs font-bold mt-1 ${
                        factor.impact === 'HIGH' ? 'text-bold-red' :
                        factor.impact === 'MEDIUM' ? 'text-gold' :
                        'text-electric-blue'
                      }`}>
                        {factor.impact} impact
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Market Inefficiency Note - Only show if valid edge exists */}
              {edgeValidation.is_valid_edge && (
                <div className="mt-3 text-xs text-gold/80 italic">
                  🔍 Market inefficiency detected: {edgeExplanation.market_inefficiency}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 animate-slide-up">
        {/* Win Probability */}
        <div className={`bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border ${
          winProb > 0.65 ? 'border-neon-green/40 shadow-lg shadow-neon-green/10' :
          winProb < 0.45 ? 'border-bold-red/40 shadow-lg shadow-bold-red/10' :
          'border-gold/20'
        } relative overflow-hidden group`}>
          {winProb > 0.65 && (
            <div className="absolute top-0 right-0 bg-neon-green text-charcoal text-xs font-bold px-2 py-1 rounded-bl-lg">
              🔥 ADVANTAGE
            </div>
          )}
          <h3 className="text-light-gray text-xs uppercase mb-2 flex items-center gap-2">
            Win Probability
            <span className="text-xs cursor-help" title="Probability of home team victory based on Monte Carlo simulations">ℹ️</span>
          </h3>
          <div className={`text-4xl font-bold font-teko ${
            winProb > 0.65 ? 'text-neon-green' :
            winProb < 0.45 ? 'text-bold-red' :
            'text-white'
          }`}>
            {(winProb * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-light-gray mt-2">{event.home_team}</div>
          {winProb > 0.65 && (
            <div className="text-xs text-neon-green/80 mt-2">Strong edge detected</div>
          )}
          {winProb < 0.45 && (
            <div className="text-xs text-bold-red/80 mt-2">Underdog scenario</div>
          )}
          {winProb >= 0.45 && winProb <= 0.65 && (
            <div className="text-xs text-electric-blue/80 mt-2">
              {winProb >= 0.48 && winProb <= 0.52 ? 'True coin-flip matchup' : `Sim edge: ${((winProb - 0.5) * 100).toFixed(1)}%`}
            </div>
          )}
          {/* Tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-4 bg-charcoal/95 border border-gold/40 rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10 backdrop-blur-sm">
            <p className="text-xs text-light-gray leading-relaxed">
              Win Probability shows the likelihood of home team victory based on Monte Carlo simulation across {simulation.iterations?.toLocaleString() || '50,000+'} game scenarios. Values above 65% indicate strong model confidence.
            </p>
          </div>
        </div>

        {/* Over/Under Total */}
        <div className={`bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border relative group ${
          overProb > 55 ? 'border-neon-green/40' :
          underProb > 55 ? 'border-bold-red/40' :
          'border-gray-400/20'
        }`}>
          <h3 className="text-light-gray text-xs uppercase mb-2 flex items-center gap-2">
            Over/Under
            <span className="text-xs cursor-help" title="Projected total points based on pace, efficiency, and Monte Carlo simulation">ℹ️</span>
          </h3>
          <div className="text-3xl font-bold text-white font-teko">
            {totalLine.toFixed(1)}
          </div>
          <div className="flex items-center justify-between mt-2 text-xs">
            <span className={overProb > 55 ? 'text-neon-green font-bold' : 'text-light-gray'}>
              O: {overProb.toFixed(1)}%
            </span>
            <span className="text-gold">|</span>
            <span className={underProb > 55 ? 'text-electric-blue font-bold' : 'text-light-gray'}>
              U: {underProb.toFixed(1)}%
            </span>
          </div>
          {overProb > 55 && (
            <>
              <div className="mt-2 text-xs text-neon-green/80">📈 Model leans Over</div>
              {(() => {
                const volatility = typeof simulation.volatility_index === 'string' ? simulation.volatility_index.toUpperCase() : 
                                  simulation.volatility_score || 'MODERATE';
                if (volatility === 'HIGH') {
                  return (
                    <div className="mt-1 text-xs text-bold-red font-semibold">
                      ⚠️ High volatility reduces reliability
                    </div>
                  );
                }
                return null;
              })()}
            </>
          )}
          {underProb > 55 && (
            <>
              <div className="mt-2 text-xs text-electric-blue/80">📉 Model leans Under</div>
              {(() => {
                const volatility = typeof simulation.volatility_index === 'string' ? simulation.volatility_index.toUpperCase() : 
                                  simulation.volatility_score || 'MODERATE';
                if (volatility === 'HIGH') {
                  return (
                    <div className="mt-1 text-xs text-bold-red font-semibold">
                      ⚠️ High volatility reduces reliability
                    </div>
                  );
                }
                return null;
              })()}
            </>
          )}
          {Math.abs(overProb - 50) < 5 && (
            <div className="mt-2 text-xs text-gold/80">⚖️ Neutral projection</div>
          )}
          <div className="text-xs text-white/50 mt-2">
            {(() => {
              const edgePoints = Math.abs((simulation.projected_score || totalLine) - totalLine);
              // If difference < 3 points, it's within noise - no statistical edge
              if (edgePoints < 3.0) {
                return (
                  <span className="text-light-gray/60">No statistical edge detected</span>
                );
              }
              return (
                <>
                  Edge vs market: <span className="text-gold font-bold">+{edgePoints.toFixed(1)} pts</span>
                </>
              );
            })()}
          </div>
          {/* Tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-4 bg-charcoal/95 border border-gold/40 rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10 backdrop-blur-sm">
            <p className="text-xs text-light-gray leading-relaxed">
              Over/Under shows projected total score compared to Vegas line. Model lean indicates statistical edge when probability exceeds 55%. Edge vs market quantifies point differential.
            </p>
          </div>
        </div>

        {/* Confidence Score */}
        <div className={`bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border relative group ${
          (simulation.confidence_score || 0.65) * 100 >= 85 ? 'border-purple-500/40 shadow-lg shadow-purple-500/10' :
          (simulation.confidence_score || 0.65) * 100 >= 70 ? 'border-gold/40' :
          'border-gold/20'
        }`}>
          <h3 className="text-light-gray text-xs uppercase mb-2 flex items-center gap-2">
            Confidence
            <span className="text-xs cursor-help" title="Confidence measures simulation stability from 0–100. Low confidence = volatile matchup. High confidence = stable, predictable outcome. Starter tier confidence capped by 10K sims. Elite tier unlocks 100K sim stability.">ℹ️</span>
          </h3>
          <div className="flex items-baseline gap-2">
            {(() => {
              // NORMALIZE: Raw cluster alignment (e.g., 3800, 5700) -> 0-100 scale
              const rawScore = simulation.confidence_score || 0.65;
              const normalizedScore = rawScore > 10 ? Math.min(100, Math.round((rawScore / 6000) * 100)) : Math.round(rawScore * 100);
              const tier = normalizedScore >= 90 ? 'S-Tier' :
                           normalizedScore >= 85 ? 'A-Tier' :
                           normalizedScore >= 70 ? 'B-Tier' :
                           normalizedScore >= 55 ? 'C-Tier' :
                           normalizedScore >= 30 ? 'D-Tier' : 'F-Tier';
              
              // Don't show green "high confidence" text for D/F tiers
              const isLowConfidence = normalizedScore < 55;
              return (
                <>
                  <div className="text-sm text-light-gray mr-2">Confidence:</div>
                  <div className={`text-4xl font-bold font-teko ${
                    normalizedScore >= 85 ? 'text-purple-400' :
                    normalizedScore >= 70 ? 'text-gold' :
                    'text-white'
                  }`}>
                    {normalizedScore}
                  </div>
                  <div className="text-sm text-light-gray">/100</div>
                  <div className={`text-lg font-bold ${
                    normalizedScore >= 85 ? 'text-purple-400' :
                    normalizedScore >= 70 ? 'text-gold' :
                    'text-light-gray'
                  }`}>
                    {tier}
                  </div>
                </>
              );
            })()}
          </div>
          {(() => {
            const rawScore = simulation.confidence_score || 0.65;
            const normalizedScore = rawScore > 10 ? Math.min(100, Math.round((rawScore / 6000) * 100)) : Math.round(rawScore * 100);
            return (
              <>
                <div className="text-xs text-white/60 mt-2 font-semibold">
                  {normalizedScore >= 85 ? 'Strong alignment across simulation clusters' :
                   normalizedScore >= 70 ? 'Good convergence across projections' :
                   normalizedScore >= 55 ? 'Moderate consensus detected' :
                   'Divergent simulations — higher variance'}
                </div>
                <div className="text-xs text-light-gray mt-1">
                  {normalizedScore >= 85 ? 'Elite alignment across simulations' :
                   normalizedScore >= 70 ? 'Strong model convergence' :
                   normalizedScore >= 55 ? 'Moderate confidence' :
                   'High variance detected'}
                </div>
                <div className="text-xs text-white/30 mt-2">
                  Derived from simulation cluster alignment strength (Tier scale: S=90-100, A=85-89, B=70-84, C=55-69, D=30-54, F=0-29)
                </div>
              </>
            );
          })()}
          
          {/* PHASE 18: Confidence Banner */}
          {confidenceTooltip && (() => {
            const rawScore = simulation.confidence_score || 0.65;
            const normalizedScore = rawScore > 10 ? Math.min(100, Math.round((rawScore / 6000) * 100)) : Math.round(rawScore * 100);
            const isLowConfidence = normalizedScore < 55; // D-Tier or F-Tier
            
            // Don't show green success banner for low confidence (D/F tiers)
            if (isLowConfidence && confidenceTooltip.banner_type === 'success') {
              return null;
            }
            
            return (
              <div className={`mt-3 p-2 rounded text-xs ${
                confidenceTooltip.banner_type === 'success' ? 'bg-neon-green/10 text-neon-green border border-neon-green/30' :
                confidenceTooltip.banner_type === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30' :
                'bg-blue-500/10 text-blue-400 border border-blue-500/30'
              }`}>
                {confidenceTooltip.banner_message}
              </div>
            );
          })()}
          
          {/* Tooltip on hover */}
          {confidenceTooltip && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-4 bg-charcoal/95 border border-gold/40 rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10 backdrop-blur-sm">
              <p className="text-xs text-light-gray leading-relaxed">
                {confidenceTooltip.tooltip}
              </p>
            </div>
          )}
        </div>

        {/* Volatility Index */}
        <div className={`bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border ${
          getVolatilityColor(volatilityIndex).includes('neon-green') ? 'border-neon-green/20' : 
          getVolatilityColor(volatilityIndex).includes('bold-red') ? 'border-bold-red/40 shadow-lg shadow-bold-red/20' : 'border-yellow-500/20'
        } relative group`}>
          <h3 className="text-light-gray text-xs uppercase mb-2 flex items-center gap-2">
            Volatility
            <span className="text-xs cursor-help" title="Game outcome variance — higher volatility means wider range of possible results">ℹ️</span>
          </h3>
          <div className={`text-2xl font-bold font-teko ${getVolatilityColor(volatilityIndex)} flex items-center gap-2`}>
            <span className="text-2xl">{getVolatilityLabel(volatilityIndex) === 'HIGH' ? '🔴' : getVolatilityIcon(volatilityIndex)}</span>
            {getVolatilityLabel(volatilityIndex)}
          </div>
          <div className="text-xs text-light-gray mt-2">Variance: {varianceValue.toFixed(2)}</div>
          <div className={`text-xs mt-1 font-semibold ${
            getVolatilityLabel(volatilityIndex) === 'HIGH' ? 'text-bold-red' :
            getVolatilityLabel(volatilityIndex) === 'LOW' ? 'text-neon-green/80' :
            'text-white/50'
          }`}>
            {getVolatilityLabel(volatilityIndex) === 'HIGH' ? '⚠️ Reduce unit sizing — high variance game' :
             getVolatilityLabel(volatilityIndex) === 'LOW' ? 'Stable scoring expected. Predictable outcome range.' :
             'Moderate variance. Standard deviation expected.'}
          </div>
          {/* Tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 p-4 bg-charcoal/95 border border-gold/40 rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10 backdrop-blur-sm">
            <p className="text-xs text-light-gray leading-relaxed mb-2">
              Volatility measures game outcome variability. HIGH volatility suggests wider scoring range and increased upset potential. LOW volatility indicates predictable, stable scoring.
            </p>
            {getVolatilityLabel(volatilityIndex) === 'HIGH' && (
              <p className="text-xs text-bold-red font-semibold mt-2 pt-2 border-t border-bold-red/30">
                ⚠️ HIGH variance impact: Consider reducing unit sizing by 25-50%. Wider confidence intervals mean higher bust risk even with statistical edge.
              </p>
            )}
          </div>
        </div>

        {/* Injury Impact */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-deep-red/20">
          <h3 className="text-light-gray text-xs uppercase mb-2">Injury Impact</h3>
          {(() => {
            const sportLabels = getSportLabels(event?.sport_key || '');
            const impactValue = simulation.injury_impact?.reduce((sum, inj) => sum + Math.abs(inj.impact_points), 0) || 0;
            return impactValue === 0 ? (
              <>
                <div className="text-3xl font-bold text-neon-green font-teko">0.0</div>
                <div className="text-xs text-neon-green mt-2">No major injuries</div>
              </>
            ) : (
              <>
                <div className="text-4xl font-bold text-deep-red font-teko">
                  {impactValue.toFixed(1)}
                </div>
                <div className="text-xs text-light-gray mt-2">{sportLabels.impactLabel}</div>
              </>
            );
          })()}
        </div>
      </div>

      {/* BEATVEGAS READ BLOCK - Required analytical summary */}
      {simulation && (
        <div className="mb-6 bg-gradient-to-br from-electric-blue/10 to-purple-900/10 border border-electric-blue/30 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="text-2xl">🎯</div>
            <h3 className="text-xl font-bold text-white font-teko">BEATVEGAS SIMULATION READ</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            {/* Side Lean */}
            <div className="bg-charcoal/50 p-4 rounded-lg">
              <div className="text-light-gray text-xs uppercase mb-2">Side Lean</div>
              <div className={`font-bold ${winProb > 0.65 ? 'text-neon-green' : winProb < 0.45 ? 'text-bold-red' : 'text-gold'}`}>
                {winProb > 0.65 ? `✅ ${event.home_team} -${((winProb - 0.5) * 20).toFixed(1)}` :
                 winProb < 0.45 ? `✅ ${event.away_team} +${((0.5 - winProb) * 20).toFixed(1)}` :
                 '⚖️ NEUTRAL (Coin flip)'}
              </div>
              <div className="text-xs text-light-gray mt-1">
                {winProb > 0.65 ? `Model favors home by ${((winProb - 0.5) * 100).toFixed(0)}%` :
                 winProb < 0.45 ? `Model favors away by ${((0.5 - winProb) * 100).toFixed(0)}%` :
                 'No statistical edge detected'}
              </div>
            </div>

            {/* Total Lean */}
            <div className="bg-charcoal/50 p-4 rounded-lg">
              <div className="text-light-gray text-xs uppercase mb-2">Total Lean</div>
              <div className={`font-bold ${overProb > 55 ? 'text-neon-green' : underProb > 55 ? 'text-electric-blue' : 'text-gold'}`}>
                {overProb > 55 ? `📈 OVER ${totalLine}` :
                 underProb > 55 ? `📉 UNDER ${totalLine}` :
                 `⚖️ NEUTRAL (${totalLine})`}
              </div>
              <div className="text-xs text-light-gray mt-1">
                {overProb > 55 ? `Model projects ${overProb.toFixed(0)}% chance of OVER` :
                 underProb > 55 ? `Model projects ${underProb.toFixed(0)}% chance of UNDER` :
                 'Projected total aligns with market'}
              </div>
            </div>

            {/* 1H Lean */}
            {firstHalfSimulation && (
              <div className="bg-charcoal/50 p-4 rounded-lg">
                <div className="text-light-gray text-xs uppercase mb-2">1H Lean</div>
                <div className="font-bold text-purple-400">
                  {firstHalfSimulation.median_total ? `${firstHalfSimulation.median_total.toFixed(1)} proj` : 'No 1H data'}
                </div>
                <div className="text-xs text-light-gray mt-1">First half projection</div>
              </div>
            )}

            {/* One-line Summary */}
            <div className="bg-charcoal/50 p-4 rounded-lg md:col-span-2">
              <div className="text-light-gray text-xs uppercase mb-2">Model Summary</div>
              <div className="text-white font-semibold">
                {(() => {
                  const rawScore = simulation.confidence_score || 0.65;
                  const normalizedScore = rawScore > 10 ? Math.min(100, Math.round((rawScore / 6000) * 100)) : Math.round(rawScore * 100);
                  const volatility = getVolatilityLabel(volatilityIndex);
                  
                  if (normalizedScore >= 70 && volatility !== 'HIGH' && Math.abs(winProb - 0.5) > 0.10) {
                    return `🔥 HIGH-CONFIDENCE SCENARIO: Model shows ${(Math.abs(winProb - 0.5) * 100).toFixed(0)}% edge with ${normalizedScore}/100 confidence. ${volatility} volatility suggests ${volatility === 'LOW' ? 'stable' : 'moderate'} outcome variance.`;
                  } else if (normalizedScore >= 55 && Math.abs(winProb - 0.5) > 0.05) {
                    return `⚡ MODERATE LEAN: ${(Math.abs(winProb - 0.5) * 100).toFixed(0)}% edge detected with ${normalizedScore}/100 confidence. ${volatility} volatility indicates ${volatility === 'HIGH' ? 'high risk' : 'manageable variance'}.`;
                  } else {
                    return `⚠️ NEUTRAL PROJECTION: No significant edge detected (${normalizedScore}/100 confidence, ${volatility} volatility). Market appears efficiently priced.`;
                  }
                })()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SIMULATION TIER NUDGE - Mandatory upgrade messaging */}
      {simulation && (
        <div className="mb-6 bg-gradient-to-r from-gold/10 to-purple-500/10 border border-gold/30 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-2xl">🧪</div>
              <div>
                <div className="text-white font-bold">
                  Sim Power: {(simulation.iterations / 1000).toFixed(0)}K ({simulation.iterations >= 100000 ? 'Elite' : simulation.iterations >= 50000 ? 'Pro' : simulation.iterations >= 25000 ? 'Core' : 'Starter'} Tier)
                </div>
                <div className="text-xs text-light-gray mt-1">
                  {simulation.iterations < 100000 ? (
                    <>
                      {simulation.iterations >= 50000 ? 'Elite' : simulation.iterations >= 25000 ? 'Pro' : 'Core'} runs {simulation.iterations >= 50000 ? '100,000' : simulation.iterations >= 25000 ? '50,000' : '25,000'} simulations for {simulation.iterations >= 50000 ? 'maximum precision' : 'higher-resolution edges'}.
                      {simulation.metadata?.user_tier !== 'elite' && ' Tighter confidence bands available.'}
                    </>
                  ) : (
                    'Maximum simulation depth — institutional-grade analysis'
                  )}
                </div>
              </div>
            </div>
            {simulation.iterations < 100000 && simulation.metadata?.user_tier !== 'elite' && (
              <button 
                onClick={() => window.location.href = '/subscription'}
                className="px-4 py-2 bg-gold text-charcoal font-bold rounded-lg hover:bg-gold/90 transition"
              >
                Upgrade
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tab Navigation - Sticky Horizontal Bar with Glow */}
      <div className="mb-6 sticky top-0 z-20 bg-charcoal/95 backdrop-blur-md -mx-6 px-6 py-2 border-b border-navy/50">
        <div className="flex space-x-2 overflow-x-auto">
          {(() => {
            const sportLabels = getSportLabels(event?.sport_key || '');
            return [
              { key: 'distribution', icon: '📊', label: 'Distribution' },
              { key: 'injuries', icon: '🏥', label: 'Injuries' },
              { key: 'props', icon: '🎯', label: 'Props' },
              { key: 'firsthalf', icon: sportLabels.headerEmoji, label: '1H Total' },
              { key: 'movement', icon: '📈', label: 'Movement' },
              { key: 'pulse', icon: '💬', label: 'Pulse' }
            ];
          })().map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as any)}
              className={`px-6 py-3 font-semibold text-sm whitespace-nowrap transition-all rounded-lg relative ${
                activeTab === key
                  ? 'text-gold bg-gold/10 shadow-lg'
                  : 'text-light-gray hover:text-white hover:bg-navy/30'
              }`}
              style={activeTab === key ? {
                boxShadow: '0 0 20px rgba(212, 166, 74, 0.4), inset 0 0 20px rgba(212, 166, 74, 0.1)'
              } : {}}
            >
              <span>{icon} {label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-charcoal rounded-xl p-6 border border-navy">
        {/* Panel 1: Score Distribution */}
        {activeTab === 'distribution' && (
          <div className="space-y-6">
            <h3 className="text-2xl font-bold text-white font-teko mb-2">
              📊 Monte Carlo Simulation ({simulation.iterations.toLocaleString()} iterations)
            </h3>
            {userTier !== 'elite' && simulation.iterations > currentIterations && (
              <p className="text-xs text-gold/80 mb-4">
                🔮 This game was simulated using {simulation.iterations >= 100000 ? 'Elite' : simulation.iterations >= 50000 ? 'Pro' : 'Starter'} depth ({simulation.iterations.toLocaleString()}) for accuracy. Upgrade to {simulation.iterations >= 100000 ? 'Elite' : 'Pro'} tier to view full raw sim data.
              </p>
            )}
            
            {/* Upgrade Prompt */}
            <UpgradePrompt
              variant="medium"
              currentTier={userTier}
              currentIterations={currentIterations}
            />
            
            {scoreDistData.length > 0 ? (
              <>
                {/* Spread Distribution Chart */}
                <div className="bg-navy/20 rounded-lg p-6 border border-gold/10">
                  <h4 className="text-lg font-semibold text-white mb-4">Margin of Victory Distribution</h4>
                  <ResponsiveContainer width="100%" height={400}>
                    <AreaChart data={scoreDistData}>
                        <defs>
                          <linearGradient id="colorDistribution" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#D4A64A" stopOpacity={0.9}/>
                          <stop offset="95%" stopColor="#D4A64A" stopOpacity={0.1}/>
                          </linearGradient>
                        </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a3a4a" strokeOpacity={0.3} />
                      <XAxis 
                        dataKey="margin" 
                        stroke="#a0aec0" 
                        label={{ value: 'Point Margin', position: 'insideBottom', offset: -5, fill: '#a0aec0' }}
                      />
                      <YAxis 
                        stroke="#a0aec0" 
                        label={{ value: 'Probability (%)', angle: -90, position: 'insideLeft', fill: '#a0aec0' }}
                      />
                        <Tooltip 
                        contentStyle={{ backgroundColor: '#0f1419', border: '1px solid #D4A64A', borderRadius: '8px' }}
                        labelStyle={{ color: '#D4A64A' }}
                      />
                      <ReferenceLine 
                        x={0} 
                        stroke="#FFD700" 
                        strokeDasharray="3 3" 
                        strokeWidth={3} 
                        label={{ 
                          value: "EVEN", 
                          fill: "#FFD700", 
                          fontSize: 14, 
                          fontWeight: 'bold',
                          position: 'top'
                        }} 
                      />
                      <Area 
                        type="monotone" 
                        dataKey="probability" 
                        stroke="#D4A64A" 
                        strokeWidth={3}
                        fill="url(#colorDistribution)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                  
                  {/* Chart Upgrade Prompt */}
                  <UpgradePrompt
                    variant="chart"
                    currentTier={userTier}
                    currentIterations={currentIterations}
                  />
                </div>

                {/* Over/Under Analysis */}
                <div className="bg-navy/30 rounded-lg p-6 mt-6">
                  <h4 className="text-lg font-semibold text-white mb-4 flex items-center">
                    <span className="mr-2">🎲</span>
                    Over/Under Total Points Analysis
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                      <div className="text-light-gray text-xs uppercase mb-2">Projected Total</div>
                      <div className="text-white font-bold text-3xl font-teko">
                        {totalScore.toFixed(1)}
                      </div>
                      <div className="text-gold text-xs mt-1">Combined Score</div>
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                      <div className="text-light-gray text-xs uppercase mb-2">Over {totalLine.toFixed(1)}</div>
                      <div className="text-neon-green font-bold text-3xl font-teko">
                        {overProb.toFixed(1)}%
                      </div>
                      <div className="text-light-gray text-xs mt-1">
                        {simulation.iterations?.toLocaleString() || '10,000'} simulations
                      </div>
                      <UpgradePrompt
                        variant="short"
                        currentTier={userTier}
                        currentIterations={currentIterations}
                        className="mt-2"
                      />
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                      <div className="text-light-gray text-xs uppercase mb-2">Under {totalLine.toFixed(1)}</div>
                      <div className="text-gold font-bold text-3xl font-teko">
                        {underProb.toFixed(1)}%
                      </div>
                      <div className="text-light-gray text-xs mt-1">{simulation.iterations?.toLocaleString() || '10,000'} simulations</div>
                    </div>
                  </div>
                </div>

                {/* Confidence Intervals */}
                <div className="bg-navy/30 rounded-lg p-6 mt-6">
                  <h4 className="text-lg font-semibold text-white mb-4 flex items-center">
                    <span className="mr-2">📐</span>
                    Statistical Confidence Intervals
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                    <div className="bg-charcoal/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-2">68% Confidence</div>
                      <div className="text-white font-bold text-lg">
                        {confidenceIntervals.ci_68[0].toFixed(1)} to {confidenceIntervals.ci_68[1].toFixed(1)}
                      </div>
                      <div className="text-neon-green text-xs mt-1">1 Standard Deviation</div>
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-2">95% Confidence</div>
                      <div className="text-white font-bold text-lg">
                        {confidenceIntervals.ci_95[0].toFixed(1)} to {confidenceIntervals.ci_95[1].toFixed(1)}
                      </div>
                      <div className="text-yellow-500 text-xs mt-1">2 Standard Deviations</div>
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-4">
                      <div className="text-light-gray text-xs uppercase mb-2">99.7% Confidence</div>
                      <div className="text-white font-bold text-lg">
                        {confidenceIntervals.ci_99[0].toFixed(1)} to {confidenceIntervals.ci_99[1].toFixed(1)}
                      </div>
                      <div className="text-bold-red text-xs mt-1">3 Standard Deviations</div>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <p className="text-light-gray text-lg mb-2">📊 No distribution data available</p>
                <p className="text-light-gray/60 text-sm">The simulation may still be processing. Try refreshing the page.</p>
                <p className="text-xs text-yellow-400/70 mt-3">Check browser console for details</p>
              </div>
            )}
            
            {/* Legal Disclaimer */}
            <div className="mt-6 bg-yellow-900/20 border border-yellow-600/30 rounded-lg p-3 text-center">
              <p className="text-xs text-yellow-200/80">
                ⚠️ This platform provides statistical modeling only. No recommendations or betting instructions are provided.
              </p>
            </div>
          </div>
        )}

        {/* Panel 2: Injury Impact Meter */}
        {activeTab === 'injuries' && (
          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              🏥 Injury Impact Analysis
            </h3>
            <UpgradePrompt variant="medium" currentTier={userTier} currentIterations={currentIterations} />
            
            {/* TEAM IMPACT SUMMARY */}
            {simulation.injury_summary && simulation.injury_impact && simulation.injury_impact.length > 0 && (
              <div className="bg-gradient-to-r from-navy/50 to-charcoal/50 rounded-lg p-6 border border-gold/30 mb-6">
                <h4 className="text-gold font-bold text-sm uppercase tracking-wider mb-4 flex items-center">
                  📊 Team Injury Impact Summary
                  <span className="ml-2 text-xs text-light-gray normal-case">
                    (Positive = benefit, Negative = hurts team)
                  </span>
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                    <div className="text-xs text-light-gray uppercase mb-1">Offensive Impact</div>
                    <div className={`text-3xl font-bold font-teko ${
                      simulation.injury_summary.total_offensive_impact >= 0 ? 'text-neon-green' : 'text-bold-red'
                    }`}>
                      {simulation.injury_summary.total_offensive_impact > 0 ? '+' : ''}
                      {simulation.injury_summary.total_offensive_impact.toFixed(1)} pts
                    </div>
                  </div>
                  <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                    <div className="text-xs text-light-gray uppercase mb-1">Defensive Impact</div>
                    <div className={`text-3xl font-bold font-teko ${
                      simulation.injury_summary.total_defensive_impact >= 0 ? 'text-neon-green' : 'text-bold-red'
                    }`}>
                      {simulation.injury_summary.total_defensive_impact > 0 ? '+' : ''}
                      {simulation.injury_summary.total_defensive_impact.toFixed(1)} pts
                    </div>
                  </div>
                  <div className="bg-charcoal/50 rounded-lg p-4 text-center border-2 border-gold/50">
                    <div className="text-xs text-gold uppercase mb-1 font-bold">Combined Net Impact</div>
                    <div className={`text-3xl font-bold font-teko ${
                      simulation.injury_summary.combined_net_impact >= 0 ? 'text-neon-green' : 'text-bold-red'
                    }`}>
                      {simulation.injury_summary.combined_net_impact > 0 ? '+' : ''}
                      {simulation.injury_summary.combined_net_impact.toFixed(1)} pts
                    </div>
                  </div>
                </div>
                <div className="mt-3 text-xs text-light-gray text-center italic">
                  {simulation.injury_summary.impact_description}
                </div>
              </div>
            )}
            
            {/* INDIVIDUAL INJURY IMPACTS */}
            {simulation.injury_impact && simulation.injury_impact.length > 0 ? (
              <>
                <h4 className="text-white font-bold text-lg mb-3">Individual Player Impacts</h4>
                {simulation.injury_impact.map((injury, idx) => {
                  // Fixed status color mapping
                  const getStatusEmoji = (status: string) => {
                    if (status === 'OUT') return '🔴';  // Red
                    if (status === 'DOUBTFUL') return '🟠';  // Orange
                    if (status === 'QUESTIONABLE') return '🟡';  // Yellow
                    return '🟢';  // Green (PROBABLE/ACTIVE)
                  };
                  
                  return (
                    <div key={idx} className="bg-navy/30 rounded-lg p-4 flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <span className="text-2xl">{getStatusEmoji(injury.status)}</span>
                          <div>
                            <div className="text-white font-bold text-lg">{injury.player}</div>
                            <div className="text-light-gray text-sm">{injury.team} • {injury.status}</div>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-3xl font-bold font-teko ${
                          injury.impact_points > 0 ? 'text-neon-green' : 'text-bold-red'
                        }`} title={injury.impact_points > 0 ? 'Positive impact for this team' : 'Negative impact for this team'}>
                          {injury.impact_points > 0 ? '+' : ''}{injury.impact_points.toFixed(1)}
                        </div>
                        <div className="text-xs text-light-gray">
                          {injury.impact_points > 0 ? '✅ Benefits Team' : '⚠️ Hurts Team'}
                        </div>
                      </div>
                      {/* Visual Impact Bar */}
                      <div className="ml-6 w-32">
                        <div className="bg-charcoal rounded-full h-4">
                          <div
                            className={`h-4 rounded-full ${
                              injury.impact_points > 0 ? 'bg-neon-green' : 'bg-bold-red'
                            }`}
                            style={{ width: `${Math.min(Math.abs(injury.impact_points) * 20, 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </>
            ) : (
              <div className="bg-navy/30 rounded-lg p-8 text-center">
                <div className="text-5xl mb-4">✅</div>
                <div className="text-xl text-white font-semibold mb-2">
                  No Major Injuries
                </div>
                <div className="text-light-gray">
                  No injuries impacting projections
                </div>
              </div>
            )}
          </div>
        )}

        {/* Panel 3: Top Props */}
        {activeTab === 'props' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-white font-teko">
                🎯 Top 5 Prop Mispricings
              </h3>
              {/* Sort Dropdown */}
              <select 
                className="bg-charcoal text-white text-sm px-4 py-2 rounded-lg border border-navy hover:border-electric-blue transition cursor-pointer"
                value={propsSortBy}
                onChange={(e) => setPropsSortBy(e.target.value)}
              >
                <option value="ev">Sort by: EV%</option>
                <option value="probability">Sort by: Win Probability</option>
                <option value="edge">Sort by: Edge Amount</option>
                <option value="projection">Sort by: AI Projection</option>
              </select>
            </div>
            <UpgradePrompt variant="props" currentTier={userTier} currentIterations={currentIterations} />
            {simulation.top_props && simulation.top_props.length > 0 ? (
              (() => {
                // Sort props based on state selection
                const sortedProps = [...simulation.top_props].sort((a, b) => {
                  if (propsSortBy === 'ev') return Math.abs(b.ev) - Math.abs(a.ev);
                  if (propsSortBy === 'probability') return b.probability - a.probability;
                  if (propsSortBy === 'edge') return Math.abs(b.edge || 0) - Math.abs(a.edge || 0);
                  if (propsSortBy === 'projection') return (b.ai_projection || 0) - (a.ai_projection || 0);
                  return 0;
                });
                
                // PHASE 15: Group props by position for sport-specific display
                const groupedProps: Record<string, any[]> = {};
                
                sortedProps.forEach((prop: any) => {
                  const position = prop.position || 'Player';
                  if (!groupedProps[position]) {
                    groupedProps[position] = [];
                  }
                  groupedProps[position].push(prop);
                });
                
                return Object.entries(groupedProps).map(([position, props]) => (
                  <div key={position} className="space-y-3">
                    {/* Position Header (Sport-Specific) */}
                    <div className="flex items-center space-x-2 mb-3">
                      <div className="h-0.5 bg-gold/30 flex-1"></div>
                      <h4 className="text-gold font-bold text-sm uppercase tracking-wider">
                        {position}
                        {position === 'Quarterback' && ' 🏈'}
                        {position === 'Running Back' && ' 🏃'}
                        {position === 'Wide Receiver' && ' 🎯'}
                        {position === 'Guard' && ' 🏀'}
                        {position === 'Forward' && ' 🔥'}
                        {position === 'Center' && ' 🦍'}
                      </h4>
                      <div className="h-0.5 bg-gold/30 flex-1"></div>
                    </div>
                    
                    {/* Props in this position */}
                    {props.map((prop, idx) => {
                      // Calculate EV if backend didn't provide it or it's 0
                      let calculatedEV = prop.ev;
                      if (calculatedEV === 0 && prop.probability && prop.line) {
                        // Assume standard -110 odds (American)
                        const americanOdds = -110;
                        const decimalOdds = americanOdds < 0 
                          ? (100 / Math.abs(americanOdds)) + 1 
                          : (americanOdds / 100) + 1;
                        
                        // EV% = (Win Probability × Payout) - (Loss Probability × Stake)
                        // For -110: payout = 0.909 units per 1 unit staked
                        const payout = decimalOdds - 1;  // Net payout (excludes stake)
                        const stake = 1;
                        const winProbability = prop.probability;
                        const lossProbability = 1 - winProbability;
                        
                        calculatedEV = ((winProbability * payout) - (lossProbability * stake)) * 100;
                      }
                      
                      // Confidence badge color
                      const getConfidenceBadge = (tier: string) => {
                        if (tier === 'Gold') return 'bg-gold/20 text-gold border-gold/50';
                        if (tier === 'Silver') return 'bg-gray-400/20 text-gray-300 border-gray-400/50';
                        return 'bg-amber-700/20 text-amber-500 border-amber-700/50';  // Bronze
                      };
                      
                      return (
                        <div key={idx} className="bg-gradient-to-r from-navy/50 to-charcoal/50 rounded-lg p-5 border border-gold/20 hover:border-gold transition">
                          {/* Header: Player Name + Confidence Badge */}
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex-1">
                              <div className="text-white font-bold text-xl">{prop.player}</div>
                              <div className="text-light-gray text-sm">
                                {prop.team} • {prop.prop_type}
                              </div>
                            </div>
                            {prop.confidence_tier && (
                              <div className={`px-3 py-1 rounded-full text-xs font-bold border ${getConfidenceBadge(prop.confidence_tier)}`}>
                                {prop.confidence_tier.toUpperCase()}
                              </div>
                            )}
                          </div>
                          
                          {/* Model Projection Distribution */}
                          {prop.lean && (
                            <div className={`inline-block px-3 py-1 rounded-full text-xs font-bold mb-3 ${
                              prop.lean === 'OVER' ? 'bg-electric-blue/20 text-electric-blue' : 'bg-purple-500/20 text-purple-300'
                            }`}>
                              Model Projection: {prop.lean} ({(prop.probability * 100).toFixed(1)}%)
                            </div>
                          )}
                          
                          {/* Line Source + AI Projection */}
                          <div className="bg-charcoal/70 rounded-lg p-3 mb-3">
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <div className="text-xs text-light-gray mb-1">Book Line</div>
                                <div className="text-gold font-bold text-2xl font-teko">{prop.line}</div>
                                {prop.book_source && (
                                  <div className="text-xs text-light-gray mt-1">
                                    {prop.book_source} • {prop.updated_at || 'Live'}
                                  </div>
                                )}
                              </div>
                              <div className="text-right">
                                <div className="text-xs text-light-gray mb-1">AI Projection</div>
                                <div className="text-electric-blue font-bold text-2xl font-teko">
                                  {prop.ai_projection || prop.line}
                                </div>
                                {prop.edge && (
                                  <div className={`text-xs font-bold mt-1 ${
                                    prop.edge > 0 ? 'text-electric-blue' : 'text-purple-400'
                                  }`}>
                                    Variance: {prop.edge > 0 ? '+' : ''}{prop.edge} pts
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                          
                          {/* Model Discrepancy Explanation */}
                          {prop.mispricing_explanation && (
                            <div className="bg-electric-blue/10 border border-electric-blue/30 rounded-lg p-3 mb-3">
                              <div className="text-xs text-light-gray uppercase mb-1">Explanation of Model Discrepancy</div>
                              <div className="text-sm text-white italic">"{prop.mispricing_explanation}"</div>
                              <div className="text-xs text-light-gray mt-1">(Shows difference between model projection & book line. Not betting value.)</div>
                            </div>
                          )}
                          
                          {/* Metrics Grid */}
                          <div className="grid grid-cols-2 gap-3">
                            <div className="bg-charcoal/50 rounded-lg p-3">
                              <div className="text-light-gray text-xs uppercase mb-1">Win Probability</div>
                              <div className="text-white font-bold text-lg">
                                {(prop.probability * 100).toFixed(1)}%
                              </div>
                            </div>
                            <div className="bg-charcoal/50 rounded-lg p-3">
                              <div className="text-light-gray text-xs uppercase mb-1">Expected Value</div>
                              <div className={`font-bold text-lg ${calculatedEV >= 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                                {calculatedEV >= 0 ? '+' : ''}{calculatedEV.toFixed(2)}%
                              </div>
                            </div>
                          </div>
                          
                          {/* Simulation Count */}
                          {prop.simulations_run && (
                            <div className="mt-3 text-center text-xs text-light-gray">
                              Simulated: {prop.simulations_run.toLocaleString()} times
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ));
              })()
            ) : (
              <div className="text-center py-12 bg-navy/20 rounded-lg border border-gold/10">
                <div className="text-5xl mb-4">🎯</div>
                <p className="text-white font-bold text-xl mb-2">No Props Available for This Game</p>
                <p className="text-light-gray text-sm max-w-md mx-auto mb-4">
                  Player prop markets have not been released by sportsbooks yet.
                </p>
                <div className="mt-4 pt-4 border-t border-navy/50">
                  <p className="text-xs text-light-gray/60 uppercase font-bold mb-1">📅 Expected Release Window</p>
                  <p className="text-electric-blue text-sm">Most prop markets open 24–48 hours before tipoff</p>
                  <p className="text-light-gray/70 text-xs mt-2">Prime-time games often release lines earlier</p>
                </div>
                <div className="mt-4 bg-gold/10 border border-gold/30 rounded-lg p-3 max-w-md mx-auto">
                  <p className="text-xs text-gold font-semibold">
                    💡 Tip: Bookmark this page and return within 24 hours of game time for AI-powered prop analysis
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Panel 4: Line Movement */}
        {activeTab === 'movement' && (
          <div className="space-y-6">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              📈 Live Line Movement (Market Agent)
            </h3>
            <UpgradePrompt variant="medium" currentTier={userTier} currentIterations={currentIterations} />
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={lineMovementData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2332" />
                <XAxis dataKey="time" stroke="#7b8a9d" />
                <YAxis stroke="#7b8a9d" domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f1419', border: '1px solid #D4A64A', borderRadius: '8px' }}
                />
                <Legend />
                <Line type="monotone" dataKey="odds" stroke="#D4A64A" strokeWidth={3} name="Market Odds" />
                <Line type="monotone" dataKey="fairValue" stroke="#7CFC00" strokeWidth={3} name="Model Estimate" />
              </LineChart>
            </ResponsiveContainer>
            <div className="bg-gradient-to-r from-electric-blue/10 to-purple-600/10 rounded-lg p-4 border border-electric-blue/30">
              <p className="text-light-gray text-sm">
                💡 <span className="font-bold text-white">Model Comparison:</span> Model estimate ({lineMovementData[lineMovementData.length - 1]?.fairValue.toFixed(2)}) is {lineMovementData[lineMovementData.length - 1]?.fairValue > lineMovementData[lineMovementData.length - 1]?.odds ? 'above' : 'below'} market odds ({lineMovementData[lineMovementData.length - 1]?.odds.toFixed(2)}), showing a variance of {Math.abs(lineMovementData[lineMovementData.length - 1]?.fairValue - lineMovementData[lineMovementData.length - 1]?.odds).toFixed(2)} points.
              </p>
            </div>
          </div>
        )}

        {/* Panel 4: First Half Total (PHASE 15) */}
        {activeTab === 'firsthalf' && (
          <div className="space-y-4">
            <UpgradePrompt variant="firsthalf" currentTier={userTier} currentIterations={currentIterations} />
            <FirstHalfAnalysis
              eventId={gameId}
              simulation={firstHalfSimulation}
              loading={firstHalfLoading}
              sportKey={event?.sport_key}
            />
          </div>
        )}

        {/* Panel 5: Community Pulse */}
        {activeTab === 'pulse' && (
          <div className="space-y-6">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              💬 Community Pulse
            </h3>
            
            {/* Data Source Disclaimer */}
            <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4 mb-4">
              <p className="text-sm text-blue-200">
                <span className="font-semibold">📊 Data Source:</span> Community Sentiment Distribution (Internal Only). 
                Not sportsbook handle or ticket data. Based on {communityPulseData.reduce((sum, item) => sum + (item.picks || 0), 0)} user submissions.
              </p>
            </div>
            
            <UpgradePrompt variant="medium" currentTier={userTier} currentIterations={currentIterations} />
            {communityPulseData.map((item, idx) => (
              <div key={idx} className="bg-navy/30 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-semibold">{item.category}</span>
                  <span className="text-gold font-bold">{item.picks}%</span>
                </div>
                <div className="bg-charcoal rounded-full h-3">
                  <div
                    className="bg-gold h-3 rounded-full transition-all"
                    style={{ width: `${item.picks}%` }}
                  />
                </div>
              </div>
            ))}
            <div className="bg-gradient-to-r from-neon-green/10 to-gold/10 rounded-lg p-4 border border-neon-green/30 mt-6">
              <p className="text-light-gray text-sm">
                📊 <span className="font-bold text-white">Consensus:</span> {communityPulseData[0].picks}% of the community is backing {event.home_team}. Sharp money appears to be {simulation.volatility_index === 'HIGH' ? 'conflicted' : 'aligned with'} the public.
              </p>
            </div>
            
            {/* Legal Disclaimer */}
            <div className="mt-4 bg-yellow-900/20 border border-yellow-600/30 rounded-lg p-3 text-center">
              <p className="text-xs text-yellow-200/80">
                ⚠️ This platform provides statistical modeling only. No recommendations or betting instructions are provided.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GameDetail;
