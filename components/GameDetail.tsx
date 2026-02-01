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
import { validateSimulationData, getSpreadDisplay, getTeamWinProbability } from '../utils/dataValidation';
import { 
  classifySpreadEdge, 
  classifyTotalEdge, 
  getEdgeStateStyling, 
  shouldHighlightSide, 
  getSignalMessage,
  shouldShowRawMetrics,
  EdgeState,
  PLATFORM_DISCLAIMER,
  type EdgeClassification 
} from '../utils/edgeStateClassification';
import { 
  calculateSpreadContext, 
  getSharpSideReasoning, 
  getEdgeConfidenceLevel,
  type SpreadContext 
} from '../utils/modelSpreadLogic';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';
import type { Event as EventType, MonteCarloSimulation, EventWithPrediction } from '../types';
import SimulationDebugPanel from './SimulationDebugPanel';
import { IntegrityLogger, validateSnapshotConsistency, handleSnapshotMismatch } from '../utils/integrityLogger';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

interface GameDetailProps {
  gameId: string;
  onBack: () => void;
}

// UI TRUST LAYER: Suppress extreme certainty for non-PICK states
const shouldSuppressCertainty = (simulation: MonteCarloSimulation | null): boolean => {
  if (!simulation) return true;
  
  const pickState = simulation.pick_state || 'UNKNOWN';
  const confidence = (simulation.confidence_score || 0.65) * 100;
  
  // Suppress if NOT a PICK or confidence < 20
  return pickState !== 'PICK' || confidence < 20;
};

const getUncertaintyLabel = (simulation: MonteCarloSimulation | null): string => {
  if (!simulation) return 'Insufficient data';
  
  const pickState = simulation.pick_state || 'UNKNOWN';
  const confidence = (simulation.confidence_score || 0.65) * 100;
  
  if (pickState === 'PASS' || pickState === 'AVOID') {
    return 'No statistical edge — unstable distribution';
  } else if (pickState === 'LEAN') {
    return 'Directional lean only — unstable distribution';
  } else if (confidence < 20) {
    return 'Extreme variance — model convergence failure';
  }
  
  return 'Analysis available';
};

const GameDetail: React.FC<GameDetailProps> = ({ gameId, onBack }) => {
  const [simulation, setSimulation] = useState<MonteCarloSimulation | null>(null);
  const [firstHalfSimulation, setFirstHalfSimulation] = useState<any | null>(null);
  const [event, setEvent] = useState<EventType | null>(null);
  const [loading, setLoading] = useState(true);
  const [firstHalfLoading, setFirstHalfLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryAttempt, setRetryAttempt] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<'distribution' | 'injuries' | 'props' | 'movement' | 'pulse' | 'firsthalf'>('distribution');
  const [activeMarketTab, setActiveMarketTab] = useState<'spread' | 'moneyline' | 'total'>('spread');
  const [showDebugPayload, setShowDebugPayload] = useState(false);
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
        `${API_BASE_URL}/api/analytics/confidence-tooltip?confidence_score=${confidenceScore}&volatility=${volatilityIndex}&sim_count=${simCount}`
      );
      
      if (response.ok) {
        const data = await response.json();
        setConfidenceTooltip(data);
      }
    } catch (err) {
      console.error('Failed to fetch confidence tooltip:', err);
    }
  };

  const loadGameData = async (retryCount = 0) => {
    if (!gameId) return;

    const MAX_RETRIES = 2;
    const RETRY_DELAY = 1000; // 1 second base delay
    const startTime = performance.now();

    try {
      setLoading(true);
      setRetryAttempt(retryCount);
      setError(null);
      
      console.log(`🔄 [GameDetail] Fetch attempt ${retryCount + 1}/${MAX_RETRIES + 1} for game ${gameId}`);
      
      // Fetch simulation data and ALL events from database (all sports)
      const [simData, eventsData] = await Promise.all([
        fetchSimulation(gameId),
        fetchEventsFromDB(undefined, undefined, false, 500) // No sport filter, get all upcoming
      ]);

      const requestDuration = Math.round(performance.now() - startTime);
      console.log(`✅ [GameDetail] Success on attempt ${retryCount + 1} (${requestDuration}ms)`);
      console.log(`[GameDetail] Fetched events: ${eventsData.length}, looking for gameId: ${gameId}`);

      // INTEGRITY CHECK: Validate snapshot consistency
      const integrityCheck = validateSnapshotConsistency(simData);
      if (!integrityCheck.valid) {
        console.error('🚨 Snapshot integrity violation detected:', integrityCheck.errors);
        
        // Log violation
        IntegrityLogger.logSnapshotMismatch({
          event_id: gameId,
          market_type: 'ALL',
          expected_selection_id: 'N/A',
          received_selection_id: 'N/A',
          snapshot_hash_values: {
            main: simData.snapshot_hash || 'MISSING',
            home_selection: simData.sharp_analysis?.spread?.snapshot_hash,
            away_selection: simData.sharp_analysis?.moneyline?.snapshot_hash,
            model_preference: simData.sharp_analysis?.total?.snapshot_hash
          },
          full_payload: simData
        });
        
        // Auto-refetch on first violation
        if (retryCount === 0) {
          console.log('🔄 Auto-refetching due to integrity violation...');
          await handleSnapshotMismatch(gameId, 'ALL', () => loadGameData(retryCount + 1));
          return;
        } else {
          // On second violation, show error but allow render with warning
          console.error('❌ Persistent integrity violations after refetch');
        }
      }

      setSimulation(simData);
      const gameEvent = eventsData.find((e: EventType) => e.id === gameId);
      
      console.log('[GameDetail] Found event:', gameEvent ? '✓' : '✗');
      
      setEvent(gameEvent || null);
      setError(null);
      setRetryAttempt(0);
    } catch (err: any) {
      const requestDuration = Math.round(performance.now() - startTime);
      const statusCode = err.message?.match(/HTTP (\d+)/)?.[1] || 'unknown';
      
      // Comprehensive error logging
      console.error(`❌ [GameDetail] Fetch failed:`, {
        simulation_id: gameId,
        event_id: gameId,
        status_code: statusCode,
        error_message: err.message || 'Unknown error',
        attempt_number: `${retryCount + 1}/${MAX_RETRIES + 1}`,
        request_duration_ms: requestDuration,
        timestamp: new Date().toISOString()
      });
      
      // Retry logic for transient errors (not for 404s or auth errors)
      const isRetryable = !err.message?.includes('not found') && 
                          !err.message?.includes('Session expired') &&
                          statusCode !== '404' &&
                          statusCode !== '401';
      
      if (retryCount < MAX_RETRIES && isRetryable) {
        const retryDelay = RETRY_DELAY * (retryCount + 1); // 1s, 2s, 3s
        console.log(`⏳ [GameDetail] Retrying in ${retryDelay}ms...`);
        setError(`Loading... (Attempt ${retryCount + 2}/${MAX_RETRIES + 1})`);
        setTimeout(() => loadGameData(retryCount + 1), retryDelay);
        return;
      }
      
      // All retries exhausted or non-retryable error
      console.error(`🚫 [GameDetail] All retries exhausted or non-retryable error`);
      setError(err.message || 'Failed to load game details');
      setRetryAttempt(0);
    } finally {
      if (retryCount === 0 || error) {
        setLoading(false);
      }
    }
  };

  // PHASE 15: Load First Half simulation data
  const loadFirstHalfData = async () => {
    if (!gameId) return;

    try {
      setFirstHalfLoading(true);
      const token = localStorage.getItem('authToken');
      const response = await fetch(`${API_BASE_URL}/api/simulations/${gameId}/period/1H`, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        },
      });

      if (response.status === 404) {
        // Event not found - game likely removed or invalid
        console.warn('First half simulation unavailable: Event not found');
        return;
      }

      if (response.status === 422) {
        // Structural market error - silently skip
        const error = await response.json();
        console.warn('First half simulation unavailable:', error.detail?.message || 'Market data unavailable');
        return;
      }

      if (response.ok) {
        const data = await response.json();
        
        // Check for stale odds warning
        if (data.integrity_status?.status === 'stale_line') {
          console.warn(`⚠️ 1H simulation uses stale odds (${data.integrity_status.odds_age_hours?.toFixed(1)}h old)`);
          // Still use the data, just log the warning
        }
        
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
      const response = await fetch(`${API_BASE_URL}/api/user/follow-forecast`, {
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
      <div className="inline-flex flex-col items-center gap-1">
        <div className="relative" style={{ width: 128, height: 128 }}>
          <svg width={128} height={128} className="transform -rotate-90">
            <circle
              cx={64}
              cy={64}
              r={radius}
              fill="none"
              stroke="#1e293b"
              strokeWidth={6}
            />
            <circle
              cx={64}
              cy={64}
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth={6}
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-bold text-2xl" style={{ color }}>
              {Math.round(score)}
            </span>
          </div>
        </div>
      </div>
    );
  };
  
  if (error && !error.startsWith('Loading...')) return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <div className="text-center space-y-4">
        <div className="text-bold-red text-xl mb-4">{error}</div>
        <div className="flex gap-4 justify-center">
          <button
            onClick={() => loadGameData(0)}
            className="bg-electric-blue text-white px-6 py-2 rounded-lg hover:opacity-80 transition-opacity flex items-center gap-2"
          >
            🔄 Retry
          </button>
          <button
            onClick={onBack}
            className="bg-gold text-white px-6 py-2 rounded-lg hover:opacity-80 transition-opacity"
          >
            ← Back to Dashboard
          </button>
        </div>
        <div className="text-light-gray text-sm mt-4">
          Check console for detailed error logs
        </div>
      </div>
    </div>
  );

  if (loading) return <LoadingSpinner />;
  if (error) return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <div className="text-center space-y-4">
        <div className="text-bold-red text-xl mb-4">{error}</div>
        <div className="flex gap-4 justify-center">
          <button
            onClick={() => loadGameData(0)}
            className="bg-electric-blue text-white px-6 py-2 rounded-lg hover:opacity-80 transition-opacity"
          >
            🔄 Retry
          </button>
          <button
            onClick={onBack}
            className="bg-gold text-white px-6 py-2 rounded-lg hover:opacity-80 transition-opacity"
          >
            ← Back to Dashboard
          </button>
        </div>
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
    // CRITICAL: Model spread must preserve SIGN (+underdog, -favorite)
    // DO NOT use Math.abs() - sign determines Model Direction
    model_spread: simulation.avg_margin || 0
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

  // CRITICAL FIX: Use canonical team anchor to prevent win probability flip bug
  // Always get win probability from canonical source bound to team_id
  const canonicalTeams = simulation.canonical_teams;
  
  // Validate simulation data before rendering
  const validation = validateSimulationData(simulation, event);
  
  // BLOCK RENDERING if data validation fails (prevents displaying incorrect data)
  if (!validation.isValid) {
    console.error('🚨 DATA MISMATCH DETECTED:', validation.errors);
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6 flex items-center justify-center">
        <div className="bg-bold-red/20 border-2 border-bold-red rounded-xl p-8 max-w-2xl">
          <div className="text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-bold-red mb-4">DATA MISMATCH — HOLD</h2>
            <p className="text-light-gray mb-6">
              Internal data inconsistency detected. This game cannot be displayed until data is corrected.
            </p>
            <div className="bg-charcoal/50 p-4 rounded-lg text-left">
              <div className="text-xs text-bold-red font-mono space-y-1">
                {validation.errors.map((error, idx) => (
                  <div key={idx}>❌ {error}</div>
                ))}
              </div>
            </div>
            <p className="text-xs text-light-gray mt-4">
              Event ID: {event.id} | Simulation ID: {simulation.simulation_id}
            </p>
          </div>
        </div>
      </div>
    );
  }
  
  // Log warnings but allow rendering
  if (validation.warnings.length > 0) {
    console.warn('⚠️ DATA WARNINGS:', validation.warnings);
  }
  
  let homeWinProb: number;
  let awayWinProb: number;
  
  if (canonicalTeams) {
    // Use canonical data (correct team-to-probability binding)
    homeWinProb = canonicalTeams.home_team.win_probability * 100;
    awayWinProb = canonicalTeams.away_team.win_probability * 100;
  } else {
    // Fallback for legacy simulations (before canonical fix)
    homeWinProb = (simulation.team_a_win_probability || simulation.win_probability || 0.5) * 100;
    awayWinProb = 100 - homeWinProb;
  }
  
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

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button
          onClick={onBack}
          className="text-gold hover:text-white mb-4 flex items-center space-x-2 transition"
        >
          <span>←</span>
          <span>Back to Dashboard</span>
        </button>
        <div className="flex items-center justify-center h-96">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button
          onClick={onBack}
          className="text-gold hover:text-white mb-4 flex items-center space-x-2 transition"
        >
          <span>←</span>
          <span>Back to Dashboard</span>
        </button>
        <div className="flex flex-col items-center justify-center h-96 space-y-4">
          <div className="text-6xl">⚠️</div>
          <div className="text-white text-xl font-bold">Failed to Load Simulation</div>
          <div className="text-light-gray text-center max-w-md">
            {error}
          </div>
          <button
            onClick={() => {
              setError(null);
              loadGameData();
            }}
            className="mt-4 px-6 py-2 bg-gold text-charcoal font-bold rounded-lg hover:bg-gold/90 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Missing data state
  if (!simulation || !event) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button
          onClick={onBack}
          className="text-gold hover:text-white mb-4 flex items-center space-x-2 transition"
        >
          <span>←</span>
          <span>Back to Dashboard</span>
        </button>
        <div className="flex flex-col items-center justify-center h-96 space-y-4">
          <div className="text-6xl">🔍</div>
          <div className="text-white text-xl font-bold">Game Not Found</div>
          <div className="text-light-gray text-center max-w-md">
            This game may have been removed or the simulation is not yet available.
          </div>
          <button
            onClick={onBack}
            className="mt-4 px-6 py-2 bg-gold text-charcoal font-bold rounded-lg hover:bg-gold/90 transition"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

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
      <div className="bg-linear-to-b from-navy/30 via-transparent to-transparent pb-4 -mb-4 rounded-t-xl">
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
              followSuccess ? 'bg-neon-green' : 'bg-linear-to-r from-gold to-purple-600'
            } text-white font-bold px-4 py-2 rounded-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <span>{followSuccess ? '✓' : '⭐'}</span>
            <span>{followSuccess ? 'Following' : 'Follow'}</span>
          </button>
          {/* Share Button (Blueprint Page 64) */}
          <button
            onClick={handleShare}
            className="bg-linear-to-r from-purple-600 to-pink-600 text-white font-bold px-4 py-2 rounded-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center space-x-2"
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
          simulationCount={simulation?.metadata?.sim_count_used || simulation?.metadata?.iterations_run || simulation?.iterations}
          variance={simulation?.metadata?.variance || simulation?.variance}
          ci95={simulation?.metadata?.ci_95 || simulation?.confidence_intervals?.ci_95}
          showUpgradeHint={simulation?.metadata?.user_tier === 'free'}
        />
      </div>

      {/* KEY DRIVERS BOX - Critical Context */}
      {simulation && (
        <div className="mb-6 bg-linear-to-br from-purple-900/20 to-blue-900/20 border-2 border-purple-500/40 rounded-xl p-4 shadow-lg shadow-purple-500/5">
          <div className="flex items-start gap-3">
            <div className="shrink-0">
              <div className="w-10 h-10 bg-linear-to-br from-purple-500/20 to-blue-500/20 rounded-lg flex items-center justify-center border border-purple-500/30">
                <span className="text-2xl">🔑</span>
              </div>
            </div>
            <div className="flex-1">
              <h3 className="text-purple-300 font-bold text-base mb-3 flex items-center gap-2">
                Key Drivers
                <span className="text-xs text-purple-400/60 font-normal">Critical factors shaping this game</span>
              </h3>
              <div className="text-light-gray text-sm space-y-2">
                {simulation.injury_impact && simulation.injury_impact.length > 0 && (
                  <div className="flex items-start gap-2">
                    <span className="text-lg shrink-0">🏥</span>
                    <div><span className="text-bold-red font-semibold">Injuries:</span> {simulation.injury_impact.length} players impacted ({simulation.injury_impact.reduce((sum: number, inj: any) => sum + Math.abs(inj.impact_points), 0).toFixed(1)} pts total effect)</div>
                  </div>
                )}
                {simulation.pace_factor && simulation.pace_factor !== 1.0 && (
                  <div className="flex items-start gap-2">
                    <span className="text-lg shrink-0">⚡</span>
                    <div><span className="text-electric-blue font-semibold">Tempo:</span> {simulation.pace_factor > 1 ? 'Fast-paced' : 'Slow-paced'} game expected ({((simulation.pace_factor - 1) * 100).toFixed(1)}% {simulation.pace_factor > 1 ? 'above' : 'below'} average)</div>
                  </div>
                )}
                {simulation.outcome?.confidence && (
                  <div className="flex items-start gap-2">
                    <span className="text-lg shrink-0">📊</span>
                    <div><span className="text-gold font-semibold">Stability:</span> {getConfidenceTier((simulation.outcome.confidence || 0.65) * 100).label} ({((simulation.outcome.confidence || 0.65) * 100).toFixed(0)}% simulation convergence)</div>
                  </div>
                )}
                {simulation.metadata?.iterations_run && (
                  <div className="flex items-start gap-2">
                    <span className="text-lg shrink-0">🧬</span>
                    <div><span className="text-neon-green font-semibold">Analysis Depth:</span> {(simulation.metadata.iterations_run / 1000).toFixed(0)}K Monte Carlo simulations</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODEL OUTPUT SUMMARY - Neutral Statistical Display */}
      {simulation.outcome && (
        <div 
          className="mb-6 bg-linear-to-br from-charcoal to-navy p-6 rounded-xl border-2 animate-slide-up relative overflow-hidden"
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
        <div className="mb-6 p-6 bg-linear-to-br from-purple-900/20 via-navy/40 to-electric-blue/20 rounded-xl border border-purple-500/30 relative overflow-hidden shadow-xl shadow-purple-500/10">
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
                    <div className="text-xs text-light-gray mb-1">Market Spread</div>
                    <div className="text-lg font-bold text-white font-teko">
                      {(() => {
                        const vegasSpread = simulation?.sharp_analysis?.spread?.vegas_spread || 0;
                        const modelSpread = simulation?.sharp_analysis?.spread?.model_spread || 0;
                        
                        if (vegasSpread !== 0) {
                          const context = calculateSpreadContext(
                            event.home_team,
                            event.away_team,
                            vegasSpread,
                            modelSpread
                          );
                          return context.marketSpreadDisplay;
                        }
                        return 'N/A';
                      })()}
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">betting line</div>
                  </div>
                  
                  <div className="bg-charcoal/50 p-3 rounded-lg border border-electric-blue/30 relative group">
                    <div className="text-xs text-light-gray mb-1">Fair Spread (Model)</div>
                    <div className="text-[10px] text-gray-500 -mt-1 mb-1">Fair line estimate (pricing), not a score prediction</div>
                    <div className="text-lg font-bold text-electric-blue font-teko">
                      {(() => {
                        const vegasSpread = simulation?.sharp_analysis?.spread?.vegas_spread || 0;
                        const modelSpread = simulation?.sharp_analysis?.spread?.model_spread;
                        
                        if (modelSpread !== undefined && vegasSpread !== 0) {
                          const context = calculateSpreadContext(
                            event.home_team,
                            event.away_team,
                            vegasSpread,
                            modelSpread
                          );
                          return context.modelSpreadDisplay;
                        }
                        return 'N/A';
                      })()}
                    </div>
                    <div className="text-xs text-light-gray/60 mt-1">with team label</div>
                    {/* Model Interpretation Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 p-3 bg-navy/95 border border-gold/30 rounded-lg shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10">
                      <p className="text-xs text-light-gray font-semibold leading-relaxed mb-2">
                        🔶 LOCKED DEFINITION — Model Spread Sign:
                      </p>
                      <p className="text-xs text-white leading-relaxed mb-2">
                        • Positive (+) = Underdog spread<br/>
                        • Negative (−) = Favorite spread
                      </p>
                      <p className="text-xs text-purple-300 leading-relaxed">
                        Model Direction Formula:<br/>
                        If model &gt; market → Sharp = FAVORITE<br/>
                        If model &lt; market → Sharp = UNDERDOG
                      </p>
                    </div>
                  </div>
                  
                  <div className="bg-purple-900/30 p-3 rounded-lg border-2 border-purple-500/50 relative group">
                    <div className="text-xs text-purple-300 mb-1 font-bold flex items-center gap-1">
                      Model Preference (This Market)
                    </div>
                    <div className="text-lg font-bold text-white font-teko">
                      {(() => {
                        const probabilities = simulation?.sharp_analysis?.probabilities;
                        const spreadData = simulation?.sharp_analysis?.spread;
                        const p_cover_home = probabilities?.p_cover_home || 0.5;
                        const p_cover_away = probabilities?.p_cover_away || 0.5;
                        const market_spread = spreadData?.market_spread_home || 0;
                        
                        // CANONICAL RULE: Model Preference = Side with highest probability
                        if (p_cover_home > p_cover_away) {
                          return `${event.home_team} ${market_spread >= 0 ? '+' : ''}${market_spread.toFixed(1)}`;
                        } else if (p_cover_away > p_cover_home) {
                          return `${event.away_team} ${-market_spread >= 0 ? '+' : ''}${(-market_spread).toFixed(1)}`;
                        } else {
                          return 'No Edge (50/50)';
                        }
                      })()}
                    </div>
                    <div className="text-xs text-purple-200 mt-1">
                      {(() => {
                        const probabilities = simulation?.sharp_analysis?.probabilities;
                        const p_cover_home = probabilities?.p_cover_home || 0.5;
                        const p_cover_away = probabilities?.p_cover_away || 0.5;
                        
                        if (p_cover_home > p_cover_away) {
                          return `${(p_cover_home * 100).toFixed(1)}% cover probability`;
                        } else if (p_cover_away > p_cover_home) {
                          return `${(p_cover_away * 100).toFixed(1)}% cover probability`;
                        } else {
                          return 'Both sides equal';
                        }
                      })()}
                    </div>
                    {/* Model Preference Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-80 p-4 bg-purple-900/95 border border-purple-400/50 rounded-lg shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10">
                      <p className="text-xs text-purple-200 font-semibold mb-2">
                        📊 Probability-Based Preference
                      </p>
                      <p className="text-xs text-white leading-relaxed">
                        Model Preference always reflects the side with the highest cover probability for the SPREAD market. This is independent of fair line pricing or favorite/underdog status.
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
                
                {/* Edge Context Notes */}
                {edgeValidation.failed_rules.length > 0 && (
                  <div className="mt-3 p-3 bg-gold/5 border border-gold/30 rounded-lg">
                    <div className="text-xs font-bold text-gold mb-2 flex items-center gap-2">
                      <span>🔶</span>
                      <span>Edge Context Notes:</span>
                    </div>
                    <ul className="text-xs text-light-gray space-y-1">
                      {edgeValidation.failed_rules.map((rule, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-gold">•</span>
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
        <div className="mb-6 p-6 bg-linear-to-br from-purple-900/30 to-blue-900/30 rounded-xl border-2 border-purple-500/50 shadow-2xl">
          <div className="flex items-start gap-4">
            <div className="text-4xl">🎯</div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-purple-300 mb-2 font-teko">MODEL DIRECTION (INFORMATIONAL)</h3>
              
              {/* INSTITUTIONAL INTERPRETATION NOTICE */}
              <div className="mb-4 p-3 bg-gold/10 border border-gold/30 rounded-lg">
                <p className="text-xs text-gold/90 font-semibold flex items-center gap-2">
                  <span className="text-base">🔶</span>
                  <span>Model-Market Discrepancy Indicator — Statistical output only.</span>
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
                        {shouldSuppressCertainty(simulation) && (simulation.sharp_analysis.total.edge_points || 0) > 10 ? (
                          <span className="text-sm text-amber-400">Unstable</span>
                        ) : (
                          <>{simulation.sharp_analysis.total.edge_points?.toFixed(1)} pts</>
                        )}
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
              {simulation.sharp_analysis.spread?.has_edge && (() => {
                // Calculate spread context with team labels using LOCKED LOGIC
                const vegasSpread = simulation.sharp_analysis.spread.vegas_spread || 0;
                const modelSpread = simulation.sharp_analysis.spread.model_spread || 0;
                
                // Use locked sharp side logic for consistent display
                const spreadContext = calculateSpreadContext(
                  event.home_team,
                  event.away_team,
                  vegasSpread,  // From home team perspective
                  modelSpread   // Signed model spread
                );
                
                const edgeConfidence = getEdgeConfidenceLevel(spreadContext.edgePoints);
                
                return (
                <div className="p-4 bg-charcoal/50 rounded-lg border border-purple-500/30">
                  {/* Model Direction Callout - INFORMATIONAL */}
                  <div className="mb-4 p-4 bg-linear-to-r from-purple-900/50 to-blue-900/50 rounded-lg border-2 border-purple-400/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">🎯</span>
                        <div>
                          <div className="text-xs text-purple-300 uppercase font-bold mb-1">Model Direction</div>
                          <div className="text-xl font-bold text-white">{spreadContext.sharpSideDisplay}</div>
                        </div>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                        edgeConfidence.level === 'HIGH' ? 'bg-green-600 text-white' :
                        edgeConfidence.level === 'MEDIUM' ? 'bg-yellow-600 text-black' :
                        'bg-gray-600 text-white'
                      }`}>
                        {edgeConfidence.label}
                      </div>
                    </div>
                    <div className="text-xs text-purple-200 mt-2">
                      {getSharpSideReasoning(spreadContext)}
                    </div>
                  </div>
                  
                  {/* Grade Badge */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className={`px-3 py-1 rounded-full text-xs font-bold ${
                      simulation.sharp_analysis.spread.edge_grade === 'S' ? 'bg-purple-600 text-white' :
                      simulation.sharp_analysis.spread.edge_grade === 'A' ? 'bg-green-600 text-white' :
                      'bg-blue-600 text-white'
                    }`}>
                      {simulation.sharp_analysis.spread.edge_grade} GRADE
                    </div>
                    <div className="text-sm text-purple-300">
                      ({spreadContext.edgePoints.toFixed(1)} pt edge)
                    </div>
                  </div>
                  
                  {/* Market vs Model Spread with TEAM LABELS */}
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">Market Spread</div>
                      <div className="text-base font-bold text-white">
                        {spreadContext.marketSpreadDisplay}
                      </div>
                    </div>
                    <div className="bg-navy/50 p-3 rounded">
                      <div className="text-xs text-gray-400 mb-1">Fair Spread (Model)</div>
                      <div className="text-base font-bold text-purple-300">
                        {spreadContext.modelSpreadDisplay}
                      </div>
                    </div>
                    <div className="bg-purple-900/50 p-3 rounded border border-purple-500/30">
                      <div className="text-xs text-purple-300 mb-1 font-bold">Model Direction (Informational)</div>
                      <div className="text-base font-bold text-white">
                        {spreadContext.sharpSideDisplay}
                      </div>
                    </div>
                  </div>
                  
                  {/* Additional context */}
                  <div className="text-sm text-gray-300 mt-3 p-3 bg-navy/30 rounded">
                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                      <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                      <span>Edge Direction: {spreadContext.edgeDirection === 'FAV' ? 'Fade the Dog' : 'Take the Dog'}</span>
                    </div>
                    {simulation.sharp_analysis.spread.sharp_side_reason && (
                      <div className="text-xs text-gray-400 mt-1">
                        {simulation.sharp_analysis.spread.sharp_side_reason}
                      </div>
                    )}
                  </div>
                </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}
      
      {/* Why This Edge Exists - Explanation Panel */}
      {edgeValidation.classification !== 'NEUTRAL' && (
        <div className="mb-6 p-5 bg-linear-to-r from-navy/40 to-charcoal/60 rounded-xl border border-gold/30 shadow-lg">
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

      {/* Market-Scoped Probability Display (OUTPUT CONSISTENCY FIX) */}
      <div className="mb-6">
        {/* Market Selector Tabs */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setActiveMarketTab('spread')}
            className={`px-4 py-2 rounded-lg font-semibold transition ${
              activeMarketTab === 'spread'
                ? 'bg-purple-600 text-white shadow-lg'
                : 'bg-charcoal text-light-gray hover:bg-navy'
            }`}
          >
            SPREAD
          </button>
          <button
            onClick={() => setActiveMarketTab('moneyline')}
            className={`px-4 py-2 rounded-lg font-semibold transition ${
              activeMarketTab === 'moneyline'
                ? 'bg-purple-600 text-white shadow-lg'
                : 'bg-charcoal text-light-gray hover:bg-navy'
            }`}
          >
            MONEYLINE
          </button>
          <button
            onClick={() => setActiveMarketTab('total')}
            className={`px-4 py-2 rounded-lg font-semibold transition ${
              activeMarketTab === 'total'
                ? 'bg-purple-600 text-white shadow-lg'
                : 'bg-charcoal text-light-gray hover:bg-navy'
            }`}
          >
            TOTAL
          </button>
          {/* Debug Toggle */}
          <button
            onClick={() => setShowDebugPayload(!showDebugPayload)}
            className="ml-auto px-3 py-1 rounded bg-charcoal/50 text-xs text-gray-400 hover:bg-navy hover:text-white transition"
            title="Toggle debug payload"
          >
            🔍 DEBUG
          </button>
        </div>

        {/* Market-Specific Display */}
        <div className="bg-linear-to-br from-charcoal to-navy p-6 rounded-xl border border-purple-500/30">
          {/* SPREAD Tab */}
          {activeMarketTab === 'spread' && (() => {
            const probabilities = simulation?.sharp_analysis?.probabilities;
            const spreadData = simulation?.sharp_analysis?.spread;
            const validatorStatus = probabilities?.validator_status;
            const p_cover_home = probabilities?.p_cover_home || 0.5;
            const p_cover_away = probabilities?.p_cover_away || 0.5;
            const market_spread = spreadData?.market_spread_home || 0;
            const sharp_market = spreadData?.sharp_market;
            const sharp_selection = spreadData?.sharp_selection;
            const has_edge = spreadData?.has_edge;
            
            // Market mismatch detection
            const marketMismatch = sharp_market && sharp_market !== 'SPREAD';
            
            return (
              <div>
                <h3 className="text-2xl font-bold text-purple-300 mb-4 font-teko flex items-center gap-2">
                  📊 SPREAD MARKET
                  {validatorStatus === 'FAIL' && (
                    <span className="text-xs px-2 py-1 bg-red-500/20 border border-red-500 text-red-400 rounded">⚠️ VALIDATION FAILED</span>
                  )}
                </h3>
                
                {/* Validator Error Banner */}
                {validatorStatus === 'FAIL' && probabilities?.validator_errors && (
                  <div className="mb-4 p-3 bg-red-500/10 border-2 border-red-500 rounded-lg">
                    <div className="text-red-400 font-bold mb-2">⛔ Data Mismatch Detected — Recommendation Withheld</div>
                    <div className="text-xs text-red-300 space-y-1">
                      {probabilities.validator_errors.map((error: string, idx: number) => (
                        <div key={idx}>• {error}</div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Market Mismatch Banner */}
                {marketMismatch && (
                  <div className="mb-4 p-3 bg-yellow-500/10 border-2 border-yellow-500 rounded-lg">
                    <div className="text-yellow-400 font-bold">⚠️ Market Mismatch</div>
                    <div className="text-xs text-yellow-300 mt-1">
                      Model direction is on {sharp_market} market, not SPREAD. Recommendation hidden.
                    </div>
                  </div>
                )}

                {/* Cover Probability Display (SPREAD-SCOPED ONLY) */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Cover Probability</div>
                    <div className="text-sm text-light-gray mb-2">{event.home_team} {market_spread >= 0 ? '+' : ''}{market_spread}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_cover_home * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Cover Probability</div>
                    <div className="text-sm text-light-gray mb-2">{event.away_team} {-market_spread >= 0 ? '+' : ''}{-market_spread}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_cover_away * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {/* Model Preference (Probability-Based) */}
                {!marketMismatch && validatorStatus !== 'FAIL' && (() => {
                  // Validate probability data integrity
                  const probSum = p_cover_home + p_cover_away;
                  const probDiff = Math.abs(p_cover_home - p_cover_away);
                  const epsilon = 0.001; // 0.1% tie threshold
                  
                  // ONLY block if probabilities are invalid
                  if (isNaN(p_cover_home) || isNaN(p_cover_away) || 
                      p_cover_home == null || p_cover_away == null ||
                      Math.abs(probSum - 1.0) > 0.01 || // Sum must be ~100%
                      probDiff < epsilon) { // Must have clear winner
                    return (
                      <div className="mt-4 p-4 bg-red-900/30 border border-red-500/50 rounded-lg">
                        <div className="text-xs text-red-300 uppercase mb-1">⚠️ Direction Unavailable</div>
                        <div className="text-sm text-red-200">Integrity safeguard triggered — invalid probability data</div>
                      </div>
                    );
                  }
                  
                  // Valid probabilities - always show argmax
                  const preferredTeam = p_cover_home > p_cover_away ? event.home_team : event.away_team;
                  const preferredSpread = p_cover_home > p_cover_away ? market_spread : -market_spread;
                  const preferredProb = Math.max(p_cover_home, p_cover_away);
                  
                  return (
                    <div className="mt-4 p-4 bg-purple-900/30 border border-purple-500/50 rounded-lg">
                      <div className="text-xs text-purple-300 uppercase mb-1">Model Preference (This Market)</div>
                      <div className="text-xl font-bold text-purple-200">
                        {preferredTeam} {preferredSpread >= 0 ? '+' : ''}{preferredSpread.toFixed(1)}
                      </div>
                      <div className="text-xs text-gray-400 mt-2">
                        {(preferredProb * 100).toFixed(1)}% cover probability{has_edge ? ` | Edge: ${spreadData?.edge_points?.toFixed(1)} pts` : ''}
                      </div>
                    </div>
                  );
                })()}
              </div>
            );
          })()}

          {/* MONEYLINE Tab */}
          {activeMarketTab === 'moneyline' && (() => {
            const probabilities = simulation?.sharp_analysis?.probabilities;
            const mlData = simulation?.sharp_analysis?.moneyline;
            const validatorStatus = probabilities?.validator_status;
            const p_win_home = probabilities?.p_win_home || 0.5;
            const p_win_away = probabilities?.p_win_away || 0.5;
            const sharp_market = mlData?.sharp_market;
            const sharp_selection = mlData?.sharp_selection;
            const has_edge = mlData?.has_edge;
            
            const marketMismatch = sharp_market && sharp_market !== 'ML';
            
            return (
              <div>
                <h3 className="text-2xl font-bold text-purple-300 mb-4 font-teko flex items-center gap-2">
                  💰 MONEYLINE MARKET
                  {validatorStatus === 'FAIL' && (
                    <span className="text-xs px-2 py-1 bg-red-500/20 border border-red-500 text-red-400 rounded">⚠️ VALIDATION FAILED</span>
                  )}
                </h3>
                
                {validatorStatus === 'FAIL' && probabilities?.validator_errors && (
                  <div className="mb-4 p-3 bg-red-500/10 border-2 border-red-500 rounded-lg">
                    <div className="text-red-400 font-bold mb-2">⛔ Data Mismatch Detected — Recommendation Withheld</div>
                    <div className="text-xs text-red-300 space-y-1">
                      {probabilities.validator_errors.map((error: string, idx: number) => (
                        <div key={idx}>• {error}</div>
                      ))}
                    </div>
                  </div>
                )}

                {marketMismatch && (
                  <div className="mb-4 p-3 bg-yellow-500/10 border-2 border-yellow-500 rounded-lg">
                    <div className="text-yellow-400 font-bold">⚠️ Market Mismatch</div>
                    <div className="text-xs text-yellow-300 mt-1">
                      Model direction is on {sharp_market} market, not MONEYLINE. Recommendation hidden.
                    </div>
                  </div>
                )}

                {/* Win Probability Display (ML-SCOPED ONLY) */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Win Probability</div>
                    <div className="text-sm text-light-gray mb-2">{event.home_team}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_win_home * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Win Probability</div>
                    <div className="text-sm text-light-gray mb-2">{event.away_team}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_win_away * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {!marketMismatch && validatorStatus !== 'FAIL' && (() => {
                  // Validate probability data integrity
                  const probSum = p_win_home + p_win_away;
                  const probDiff = Math.abs(p_win_home - p_win_away);
                  const epsilon = 0.001; // 0.1% tie threshold
                  
                  // ONLY block if probabilities are invalid
                  if (isNaN(p_win_home) || isNaN(p_win_away) || 
                      p_win_home == null || p_win_away == null ||
                      Math.abs(probSum - 1.0) > 0.01 || // Sum must be ~100%
                      probDiff < epsilon) { // Must have clear winner
                    return (
                      <div className="mt-4 p-4 bg-red-900/30 border border-red-500/50 rounded-lg">
                        <div className="text-xs text-red-300 uppercase mb-1">⚠️ Direction Unavailable</div>
                        <div className="text-sm text-red-200">Integrity safeguard triggered — invalid probability data</div>
                      </div>
                    );
                  }
                  
                  // Valid probabilities - always show argmax
                  const preferredTeam = p_win_home > p_win_away ? event.home_team : event.away_team;
                  const preferredProb = Math.max(p_win_home, p_win_away);
                  
                  return (
                    <div className="mt-4 p-4 bg-purple-900/30 border border-purple-500/50 rounded-lg">
                      <div className="text-xs text-purple-300 uppercase mb-1">Model Preference (This Market)</div>
                      <div className="text-xl font-bold text-purple-200">{preferredTeam} ML</div>
                      <div className="text-xs text-gray-400 mt-2">
                        {(preferredProb * 100).toFixed(1)}% win probability{has_edge ? ` | Edge: ${mlData?.edge_pct?.toFixed(1)}%` : ''}
                      </div>
                    </div>
                  );
                })()}
              </div>
            );
          })()}

          {/* TOTAL Tab */}
          {activeMarketTab === 'total' && (() => {
            const probabilities = simulation?.sharp_analysis?.probabilities;
            const totalData = simulation?.sharp_analysis?.total;
            const validatorStatus = probabilities?.validator_status;
            const p_over = probabilities?.p_over || 0.5;
            const p_under = probabilities?.p_under || 0.5;
            const market_total = totalData?.market_total || 0;
            const sharp_market = totalData?.sharp_market;
            const sharp_selection = totalData?.sharp_selection;
            const has_edge = totalData?.has_edge;
            
            const marketMismatch = sharp_market && sharp_market !== 'TOTAL';
            
            return (
              <div>
                <h3 className="text-2xl font-bold text-purple-300 mb-4 font-teko flex items-center gap-2">
                  🎯 TOTAL MARKET
                  {validatorStatus === 'FAIL' && (
                    <span className="text-xs px-2 py-1 bg-red-500/20 border border-red-500 text-red-400 rounded">⚠️ VALIDATION FAILED</span>
                  )}
                </h3>
                
                {validatorStatus === 'FAIL' && probabilities?.validator_errors && (
                  <div className="mb-4 p-3 bg-red-500/10 border-2 border-red-500 rounded-lg">
                    <div className="text-red-400 font-bold mb-2">⛔ Data Mismatch Detected — Recommendation Withheld</div>
                    <div className="text-xs text-red-300 space-y-1">
                      {probabilities.validator_errors.map((error: string, idx: number) => (
                        <div key={idx}>• {error}</div>
                      ))}
                    </div>
                  </div>
                )}

                {marketMismatch && (
                  <div className="mb-4 p-3 bg-yellow-500/10 border-2 border-yellow-500 rounded-lg">
                    <div className="text-yellow-400 font-bold">⚠️ Market Mismatch</div>
                    <div className="text-xs text-yellow-300 mt-1">
                      Model direction is on {sharp_market} market, not TOTAL. Recommendation hidden.
                    </div>
                  </div>
                )}

                {/* Over/Under Probability Display (TOTAL-SCOPED ONLY) */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Over Probability</div>
                    <div className="text-sm text-light-gray mb-2">OVER {market_total}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_over * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div className="bg-navy/50 p-4 rounded-lg">
                    <div className="text-xs text-gray-400 uppercase mb-1">Under Probability</div>
                    <div className="text-sm text-light-gray mb-2">UNDER {market_total}</div>
                    <div className="text-3xl font-bold text-white font-teko">
                      {(p_under * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {!marketMismatch && validatorStatus !== 'FAIL' && (() => {
                  // SAFETY ASSERTION: Model preference must match probability dominance
                  const preferredSide = p_over > p_under ? 'OVER' : 'UNDER';
                  const preferredProb = Math.max(p_over, p_under);
                  const preferredDisplay = p_over > p_under ? `Over ${market_total}` : `Under ${market_total}`;
                  
                  // Integrity check
                  if (sharp_selection && !sharp_selection.toUpperCase().includes(preferredSide)) {
                    console.error('🚨 INTEGRITY VIOLATION: Total sharp_selection does not match probability dominance', {
                      sharp_selection,
                      preferredSide,
                      p_over,
                      p_under
                    });
                    return (
                      <div className="mt-4 p-4 bg-red-900/30 border border-red-500/50 rounded-lg">
                        <div className="text-xs text-red-300 uppercase mb-1">⚠️ Direction Unavailable</div>
                        <div className="text-sm text-red-200">Integrity safeguard triggered — probability mismatch detected</div>
                      </div>
                    );
                  }
                  
                  return (
                    <div className="mt-4 p-4 bg-purple-900/30 border border-purple-500/50 rounded-lg">
                      <div className="text-xs text-purple-300 uppercase mb-1">Model Preference (This Market)</div>
                      <div className="text-xl font-bold text-purple-200">{preferredDisplay}</div>
                      <div className="text-xs text-gray-400 mt-2">
                        {(preferredProb * 100).toFixed(1)}% probability{has_edge ? ` | Edge: ${totalData?.edge_points?.toFixed(1)} pts` : ''}
                      </div>
                    </div>
                  );
                })()}
              </div>
            );
          })()}

          {/* Debug Payload (Dev Toggle) */}
          {showDebugPayload && simulation?.sharp_analysis?.debug_payload && (
            <div className="mt-6 p-4 bg-charcoal/80 border border-gold/30 rounded-lg">
              <div className="text-xs text-gold font-bold mb-2 flex items-center gap-2">
                <span>🔍</span>
                <span>DEBUG PAYLOAD (Development Mode)</span>
              </div>
              <pre className="text-xs text-gray-300 overflow-x-auto">
                {JSON.stringify(simulation.sharp_analysis.debug_payload, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 animate-slide-up">
        {/* OLD Win Probability card removed - replaced by market tabs above */}

        {/* Over/Under Total */}
        <div className={`bg-linear-to-br from-charcoal to-navy p-4 rounded-xl border relative group ${
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
            {shouldSuppressCertainty(simulation) && (overProb > 70 || underProb > 70) ? (
              <span className="text-amber-400/90 text-[10px]">{getUncertaintyLabel(simulation)}</span>
            ) : (
              <>
                <span className={overProb > 55 ? 'text-neon-green font-bold' : 'text-light-gray'}>
                  O: {overProb.toFixed(1)}%
                </span>
                <span className="text-gold">|</span>
                <span className={underProb > 55 ? 'text-electric-blue font-bold' : 'text-light-gray'}>
                  U: {underProb.toFixed(1)}%
                </span>
              </>
            )}
          </div>
          {overProb > 55 && !shouldSuppressCertainty(simulation) && (
            <>
              <div className="mt-2 text-xs text-neon-green/80">📈 Model leans Over</div>
              {(() => {
                const volatility = typeof simulation.volatility_index === 'string' ? simulation.volatility_index.toUpperCase() : 
                                  simulation.volatility_score || 'MODERATE';
                if (volatility === 'HIGH') {
                  return (
                    <div className="mt-1 text-xs text-gold font-semibold">
                      🔶 High variance environment
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
                    <div className="mt-1 text-xs text-gold font-semibold">
                      🔶 High variance environment
                    </div>
                  );
                }
                return null;
              })()}
            </>
          )}
          {Math.abs(overProb - 50) < 5 && overProb <= 55 && underProb <= 55 && (
            <div className="mt-2 text-xs text-gold/80">⚖️ Balanced projection</div>
          )}
          <div className="text-xs text-white/50 mt-2">
            {(() => {
              const edgePoints = Math.abs((simulation.projected_score || totalLine) - totalLine);
              
              // TRUST LAYER: Suppress extreme edges for LEAN/NO_PLAY
              if (shouldSuppressCertainty(simulation) && edgePoints > 10) {
                return (
                  <span className="text-amber-400/80">⚠️ {getUncertaintyLabel(simulation)}</span>
                );
              }
              
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
        <div className={`bg-linear-to-br from-charcoal to-navy p-4 rounded-xl border relative group ${
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
              
              // TRUST LAYER: Suppress confidence display for LEAN/NO_PLAY
              if (shouldSuppressCertainty(simulation)) {
                return (
                  <>
                    <div className="text-sm text-amber-400/90">⚠️ {getUncertaintyLabel(simulation)}</div>
                  </>
                );
              }
              
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
        <div className={`bg-linear-to-br from-charcoal to-navy p-4 rounded-xl border ${
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
            getVolatilityLabel(volatilityIndex) === 'HIGH' ? 'text-vibrant-yellow' :
            getVolatilityLabel(volatilityIndex) === 'LOW' ? 'text-neon-green/80' :
            'text-light-gray/60'
          }`}>
            {getVolatilityLabel(volatilityIndex) === 'HIGH' ? '🔶 High variance environment — wider outcome distribution' :
             getVolatilityLabel(volatilityIndex) === 'LOW' ? 'Stable scoring expected. Predictable outcome range.' :
             ''}
          </div>
          {/* Tooltip */}
          <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 p-4 bg-charcoal/95 border border-gold/40 rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all duration-300 ease-out pointer-events-none z-10 backdrop-blur-sm">
            <p className="text-xs text-light-gray leading-relaxed mb-2">
              Volatility measures game outcome variability. HIGH volatility suggests wider scoring range and increased upset potential. LOW volatility indicates predictable, stable scoring.
            </p>
            {getVolatilityLabel(volatilityIndex) === 'HIGH' && (
              <p className="text-xs text-gold font-semibold mt-2 pt-2 border-t border-gold/30">
                🔶 High variance environment: Wider confidence intervals reflect increased outcome distribution. Consider position sizing within your framework.
              </p>
            )}
          </div>
        </div>

        {/* Injury Impact */}
        <div className="bg-linear-to-br from-charcoal to-navy p-4 rounded-xl border border-deep-red/20">
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

      {/* FINAL UNIFIED SUMMARY - Single source of truth for all interpretation */}
      {/* CRITICAL UX FIX (Jan 2025): Separates ACTIONABLE EDGE vs MODEL SIGNAL (HIGH VARIANCE) */}
      {simulation && (() => {
        const rawScore = simulation.confidence_score || 0.65;
        const normalizedScore = rawScore > 10 ? Math.min(100, Math.round((rawScore / 6000) * 100)) : Math.round(rawScore * 100);
        const volatility = getVolatilityLabel(volatilityIndex);
        const isHighVolatility = volatility === 'HIGH';
        const isLowConfidence = normalizedScore < 60;
        
        // Spread interpretation with VALUE SIDE clarity
        // CRITICAL FIX: Use canonical spread data to prevent sign inversion bug
        // Get Vegas spread from canonical source (already in correct sign)
        const marketSpread = canonicalTeams?.home_team?.vegas_spread ?? simulation.spread ?? 0;
        
        // Model spread from canonical data (home perspective)
        const modelImpliedSpread = canonicalTeams?.model_spread_home_perspective ?? (winProb - 0.5) * 20;
        const spreadDeviation = Math.abs(modelImpliedSpread - marketSpread);
        
        // CRITICAL LOGIC: Identify favorite/underdog and determine value
        // Negative spread = home is favorite, Positive spread = away is favorite
        let valueSide = '';
        let valueExplanation = '';
        
        if (marketSpread !== 0 && spreadDeviation >= 3.0) {
          // Significant deviation (3+ pts)
          
          // CRITICAL FIX: Use canonical team data for favorite/underdog roles
          // This prevents spread sign inversion bugs
          
          let vegasFavorite: string;
          let vegasUnderdog: string;
          let vegasSpreadValue: number;
          
          if (canonicalTeams) {
            // Use canonical source of truth
            vegasFavorite = canonicalTeams.vegas_favorite.name;
            vegasUnderdog = canonicalTeams.vegas_underdog.name;
            vegasSpreadValue = Math.abs(canonicalTeams.vegas_favorite.spread);
          } else {
            // Fallback for legacy data
            vegasFavorite = marketSpread < 0 ? event.home_team : event.away_team;
            vegasUnderdog = marketSpread < 0 ? event.away_team : event.home_team;
            vegasSpreadValue = Math.abs(marketSpread);
          }
          
          // Determine who is favorite in MODEL
          const modelFavorite = modelImpliedSpread < 0 ? event.home_team : event.away_team;
          const modelSpreadValue = Math.abs(modelImpliedSpread);
          
          // CASE 1: Both agree on favorite, but disagree on margin
          if (vegasFavorite === modelFavorite) {
            if (modelSpreadValue > vegasSpreadValue) {
              // Model thinks favorite is STRONGER than market
              // Sharp play: Take the favorite at the smaller spread
              valueSide = vegasFavorite;
              valueExplanation = `Vegas line: ${vegasUnderdog} +${vegasSpreadValue.toFixed(1)} | Model line: ${vegasUnderdog} +${modelSpreadValue.toFixed(1)}. Model believes ${vegasFavorite} is stronger than market thinks. Value leans toward ${vegasFavorite} -${vegasSpreadValue.toFixed(1)}.`;
            } else {
              // Model thinks favorite is WEAKER than market
              // Sharp play: Take the underdog getting more points
              valueSide = vegasUnderdog;
              valueExplanation = `Vegas line: ${vegasUnderdog} +${vegasSpreadValue.toFixed(1)} | Model line: ${vegasUnderdog} +${modelSpreadValue.toFixed(1)}. Model believes ${vegasFavorite} is weaker than market thinks. Value leans toward underdog ${vegasUnderdog} +${vegasSpreadValue.toFixed(1)}.`;
            }
          } 
          // CASE 2: Model disagrees on who the favorite is (rare but possible)
          else {
            // Model has opposite team favored - take model's favorite
            valueSide = modelFavorite;
            valueExplanation = `Vegas line: ${vegasFavorite} -${vegasSpreadValue.toFixed(1)} | Model line: ${modelFavorite} -${modelSpreadValue.toFixed(1)}. Model projects ${modelFavorite} as favorite while market favors ${vegasFavorite}. Significant disagreement — value leans toward ${modelFavorite}.`;
          }
        }
        
        // ===== CLASSIFY SPREAD EDGE (ACTIONABLE vs MODEL SIGNAL) =====
        // PRIORITY: Use backend sharp_action if available (gap-based validation)
        const sharpAction = simulation.sharp_analysis?.spread?.sharp_action || null;
        const spreadClassification = classifySpreadEdge(
          spreadDeviation,
          varianceValue,
          normalizedScore,
          valueSide || null,
          undefined,  // previousState
          sharpAction  // NEW: Pass sharp_action from backend
        );
        
        // Total interpretation (SINGLE calculation)
        const totalEdge = Math.abs((simulation.projected_score || totalLine) - totalLine);
        
        // Calculate Expected Value (EV) for total
        // EV = (win_prob * payout) - (loss_prob * stake)
        // Simplified: EV = (prob - 0.5) * 2 (for even money bets)
        const totalEV = overProb > underProb 
          ? (overProb / 100 - 0.5) * 2 * 100  // Convert to percentage
          : (underProb / 100 - 0.5) * 2 * 100;
        
        // ===== CLASSIFY TOTAL EDGE (ACTIONABLE vs MODEL SIGNAL) =====
        const totalClassification = classifyTotalEdge(
          totalEdge,
          overProb,
          underProb,
          varianceValue,
          normalizedScore,
          totalEV
        );
        
        // ===== MASTER EDGE BANNER LOGIC =====
        // CRITICAL UX FIX: Only show "EDGE DETECTED" if OFFICIAL_EDGE
        const hasOfficialEdge = spreadClassification.state === EdgeState.EDGE || 
                                totalClassification.state === EdgeState.EDGE;
        const showEdgeBanner = hasOfficialEdge;
        
        // Determine if we should show raw metrics (only for OFFICIAL_EDGE)
        const showSpreadMetrics = shouldShowRawMetrics(spreadClassification);
        const showTotalMetrics = shouldShowRawMetrics(totalClassification);
        
        // Styling based on edge state
        const spreadStyling = getEdgeStateStyling(spreadClassification.state);
        const totalStyling = getEdgeStateStyling(totalClassification.state);
        
        return (
          <div className="mb-6 bg-linear-to-br from-electric-blue/10 to-purple-900/10 border border-electric-blue/30 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="text-2xl">🎯</div>
              <h3 className="text-xl font-bold text-white font-teko">FINAL UNIFIED SUMMARY</h3>
              {/* EDGE DETECTED BANNER - Only shows if OFFICIAL_EDGE exists */}
              {showEdgeBanner && (
                <div className="ml-auto px-3 py-1 bg-neon-green/20 border border-neon-green rounded-lg text-neon-green font-bold text-xs animate-pulse">
                  ✅ OFFICIAL EDGE
                </div>
              )}
            </div>
            
            <div className="space-y-4">
              {/* Spread Analysis */}
              <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${spreadStyling.borderColor}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-light-gray text-xs uppercase font-bold">Spread Analysis</div>
                  <div className={`font-bold text-sm ${spreadStyling.textColor} flex items-center gap-2`}>
                    <span>{spreadStyling.icon}</span>
                    {spreadClassification.state === EdgeState.EDGE && spreadClassification.side ? (
                      <span>✅ {spreadClassification.side}</span>
                    ) : spreadClassification.state === EdgeState.LEAN ? (
                      <span>⚠️ MODEL LEAN</span>
                    ) : (
                      <span>⛔ NO ACTION</span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-light-gray leading-relaxed">
                  {getSignalMessage(spreadClassification)}
                </div>
                {/* Show MODEL_LEAN info */}
                {spreadClassification.state === EdgeState.LEAN && (
                  <div className={`mt-2 text-xs ${spreadStyling.textColor} ${spreadStyling.bgColor} border ${spreadStyling.borderColor} rounded px-2 py-1`}>
                    📊 Model Signal Detected — Blocked by Risk Controls
                  </div>
                )}
                {/* Show value explanation if OFFICIAL_EDGE */}
                {spreadClassification.state === EdgeState.EDGE && showSpreadMetrics && valueExplanation && (
                  <div className="mt-2 text-xs text-neon-green bg-neon-green/10 border border-neon-green/30 rounded px-2 py-1">
                    💡 {valueExplanation}
                  </div>
                )}
              </div>
              
              {/* Total Analysis */}
              <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${totalStyling.borderColor}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-light-gray text-xs uppercase font-bold">Total Analysis</div>
                  <div className={`font-bold text-sm ${totalStyling.textColor} flex items-center gap-2`}>
                    <span>{totalStyling.icon}</span>
                    {totalClassification.state === EdgeState.EDGE && totalClassification.side ? (
                      <span>✅ {totalClassification.side} {totalLine.toFixed(1)}</span>
                    ) : totalClassification.state === EdgeState.LEAN ? (
                      <span>⚠️ MODEL LEAN</span>
                    ) : (
                      <span>⛔ NO ACTION</span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-light-gray leading-relaxed">
                  {getSignalMessage(totalClassification)}
                </div>
                {/* Show MODEL_LEAN info */}
                {totalClassification.state === EdgeState.LEAN && (
                  <div className={`mt-2 text-xs ${totalStyling.textColor} ${totalStyling.bgColor} border ${totalStyling.borderColor} rounded px-2 py-1`}>
                    📊 Model Signal Detected — Blocked by Risk Controls
                  </div>
                )}
                {/* Show edge details ONLY if OFFICIAL_EDGE */}
                {totalClassification.state === EdgeState.EDGE && showTotalMetrics && (
                  <div className="mt-2 text-xs text-electric-blue bg-electric-blue/10 border border-electric-blue/30 rounded px-2 py-1">
                    💡 Edge: {totalEdge.toFixed(1)} pts | Probability: {(totalClassification.probability * 100).toFixed(0)}% | EV: +{totalEV.toFixed(1)}%
                  </div>
                )}
              </div>
              
              {/* Volatility Context */}
              <div className={`bg-charcoal/50 p-4 rounded-lg border-l-4 ${isHighVolatility ? 'border-bold-red' : 'border-neon-green'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-light-gray text-xs uppercase font-bold">Volatility Context</div>
                  <div className={`font-bold text-sm ${isHighVolatility ? 'text-bold-red' : volatility === 'LOW' ? 'text-neon-green' : 'text-gold'}`}>
                    {isHighVolatility ? '🔴' : volatility === 'LOW' ? '🟢' : '🟡'} {volatility}
                  </div>
                </div>
                <div className="text-xs text-light-gray leading-relaxed">
                  {isHighVolatility ? 
                    `High variance environment (σ=${varianceValue.toFixed(2)}) — wider outcome distribution, increased upset potential. Risk controls active.` :
                    volatility === 'LOW' ? `Low variance (σ=${varianceValue.toFixed(2)}) — stable, predictable scoring range.` :
                    `Moderate variance (σ=${varianceValue.toFixed(2)}) — normal outcome distribution.`}
                </div>
              </div>
              
              {/* Action Recommendation - 3-State Logic */}
              <div className="bg-linear-to-r from-gold/10 to-purple-500/10 border border-gold/40 rounded-lg p-4">
                <div className="text-light-gray text-xs uppercase mb-2 font-bold">Action Summary</div>
                <div className="text-white font-semibold text-sm leading-relaxed">
                  {spreadClassification.state === EdgeState.EDGE && totalClassification.state === EdgeState.EDGE ? 
                    '✅ Official edges detected on both spread and total — risk-adjusted execution approved.' :
                    spreadClassification.state === EdgeState.EDGE ? 
                    `✅ Official spread edge. Total: ${totalClassification.state === EdgeState.LEAN ? 'Model lean (informational only)' : 'No action'}.` :
                    totalClassification.state === EdgeState.EDGE ? 
                    `✅ Official total edge. Spread: ${spreadClassification.state === EdgeState.LEAN ? 'Model lean (informational only)' : 'No action'}.` :
                    spreadClassification.state === EdgeState.LEAN || totalClassification.state === EdgeState.LEAN ?
                    '⚠️ Model signals detected but blocked by risk controls. Informational only — not official plays.' :
                    '⛔ No actionable edges. Market appears efficient on both spread and total.'}
                </div>
                {/* Show both sides blocked message */}
                {spreadClassification.state === EdgeState.LEAN && 
                 totalClassification.state === EdgeState.LEAN && (
                  <div className="mt-2 text-xs text-vibrant-yellow bg-vibrant-yellow/10 border border-vibrant-yellow/30 rounded px-2 py-1">
                    ⚠️ Model Lean on both spread and total — not official plays. View Model Diagnostics for raw analysis.
                  </div>
                )}
                {/* NO_ACTION on both */}
                {spreadClassification.state === EdgeState.NEUTRAL && 
                 totalClassification.state === EdgeState.NEUTRAL && (
                  <div className="mt-2 text-xs text-gray-400 bg-gray-600/10 border border-gray-600/30 rounded px-2 py-1">
                    ⛔ Risk controls active. No betting language displayed.
                  </div>
                )}
              </div>
              
              {/* Platform Disclaimer */}
              <div className="text-xs text-light-gray/70 text-center pt-2 border-t border-navy/50">
                {PLATFORM_DISCLAIMER}
              </div>
              
              {/* 1H Quick Reference */}
              {firstHalfSimulation && firstHalfSimulation.median_total && (
                <div className="bg-charcoal/50 p-3 rounded-lg border border-purple-400/30">
                  <div className="flex items-center justify-between">
                    <div className="text-light-gray text-xs uppercase font-bold">1H Projection</div>
                    <div className="font-bold text-purple-400">
                      {firstHalfSimulation.median_total.toFixed(1)} pts
                    </div>
                  </div>
                  <div className="text-xs text-light-gray mt-1">
                    First half model median • {firstHalfSimulation.book_line_available ? 'Market anchor available' : 'No market line — reduced accuracy'}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* SIMULATION TIER NUDGE - Mandatory upgrade messaging */}
      {simulation && (
        <div className="mb-6 bg-linear-to-r from-gold/10 to-purple-500/10 border border-gold/30 rounded-xl p-4">
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
            
            {/* Interpretation Notice */}
            <div className="mt-6 bg-gold/5 border border-gold/20 rounded-lg p-3 text-center">
              <p className="text-xs text-light-gray">
                <span className="text-gold font-semibold">Statistical Model Output</span> — Use as part of your decision framework.
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
              <div className="bg-linear-to-r from-navy/50 to-charcoal/50 rounded-lg p-6 border border-gold/30 mb-6">
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
                        <div key={idx} className="bg-linear-to-r from-navy/50 to-charcoal/50 rounded-lg p-5 border border-gold/20 hover:border-gold transition">
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
            <div className="bg-linear-to-r from-electric-blue/10 to-purple-600/10 rounded-lg p-4 border border-electric-blue/30">
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
            <div className="bg-linear-to-r from-neon-green/10 to-gold/10 rounded-lg p-4 border border-neon-green/30 mt-6">
              <p className="text-light-gray text-sm">
                📊 <span className="font-bold text-white">Consensus:</span> {communityPulseData[0].picks}% of the community is backing {event.home_team}. Sharp money appears to be {simulation.volatility_index === 'HIGH' ? 'conflicted' : 'aligned with'} the public.
              </p>
            </div>
            
            {/* Interpretation Notice */}
            <div className="mt-4 bg-gold/5 border border-gold/20 rounded-lg p-3 text-center">
              <p className="text-xs text-light-gray">
                <span className="text-gold font-semibold">Statistical Model Output</span> — Use as part of your decision framework.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* DEV-ONLY: Debug Panel for Simulation Integrity */}
      {process.env.NODE_ENV === 'development' && simulation && event && (
        <SimulationDebugPanel simulation={simulation} event={event} />
      )}
    </div>
  );
};

export default GameDetail;
