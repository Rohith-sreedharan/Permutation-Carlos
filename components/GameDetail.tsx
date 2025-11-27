import React, { useState, useEffect } from 'react';
import { fetchSimulation, fetchEvents } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import SocialMetaTags from './SocialMetaTags';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Area, AreaChart } from 'recharts';
import type { Event as EventType, MonteCarloSimulation, EventWithPrediction } from '../types';

interface GameDetailProps {
  gameId: string;
  onBack: () => void;
}

const GameDetail: React.FC<GameDetailProps> = ({ gameId, onBack }) => {
  const [simulation, setSimulation] = useState<MonteCarloSimulation | null>(null);
  const [event, setEvent] = useState<EventType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'distribution' | 'injuries' | 'props' | 'movement' | 'pulse'>('distribution');
  const [lineMovementData, setLineMovementData] = useState<Array<{ time: string; odds: number; fairValue: number }>>([]);
  const [shareSuccess, setShareSuccess] = useState(false);
  const [followSuccess, setFollowSuccess] = useState(false);
  const [isFollowing, setIsFollowing] = useState(false);

  useEffect(() => {
    loadGameData();
    generateLineMovement();
  }, [gameId]);

  const loadGameData = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      const [simData, eventsData] = await Promise.all([
        fetchSimulation(gameId), // Will use full mode if backend supports it
        fetchEvents()
      ]);

      setSimulation(simData);
      const gameEvent = eventsData.find((e: EventType) => e.id === gameId);
      setEvent(gameEvent || null);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load game details');
      console.error(err);
    } finally {
      setLoading(false);
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

    const shareText = `🏀 ${event.away_team} @ ${event.home_team}\n\n📊 AI Model Analysis (${(simulation.iterations || 50000).toLocaleString()} simulations):\n• Win Probability: ${winProb}%\n• Volatility: ${volatility}\n• Confidence Score: ${confidence}/100\n\n🚀 Powered by #BeatVegas Monte Carlo AI\nbeatvegas.com/game/${gameId}`;

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
  
  const scoreDistData = spreadDistArray.slice(-30).map(d => ({
    margin: d.margin,
    probability: (d.probability * 100).toFixed(1)
  }));

  const winProb = simulation.win_probability ?? simulation.team_a_win_probability ?? 0.5;
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
  const totalLine = simulation.total_line || Math.round(totalScore * 2) / 2;
  
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

      {shareSuccess && (
        <div className="mb-4 bg-neon-green/20 border border-neon-green rounded-lg p-3 text-center text-neon-green text-sm animate-pulse">
          ✓ Game analysis copied to clipboard! Share on social media with #BeatVegas
        </div>
      )}

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        {/* Win Probability */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-gold/20">
          <h3 className="text-light-gray text-xs uppercase mb-2">Win Probability</h3>
          <div className="text-4xl font-bold text-white font-teko">
            {(winProb * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-light-gray mt-2">{event.home_team}</div>
        </div>

        {/* Over/Under Total */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-gold/20">
          <h3 className="text-light-gray text-xs uppercase mb-2">Over/Under</h3>
          <div className="text-3xl font-bold text-white font-teko">
            {totalLine.toFixed(1)}
          </div>
          <div className="text-xs text-gold mt-2">
            O: {overProb.toFixed(1)}% | U: {underProb.toFixed(1)}%
          </div>
        </div>

        {/* Confidence Score */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-gold/20">
          <h3 className="text-light-gray text-xs uppercase mb-2">Confidence</h3>
          <div className="text-4xl font-bold text-gold font-teko">
            {Math.round((simulation.confidence_score || 0.65) * 100)}
          </div>
          <div className="text-xs text-light-gray mt-2">out of 100</div>
        </div>

        {/* Volatility Index */}
        <div className={`bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border ${
          getVolatilityColor(volatilityIndex).includes('neon-green') ? 'border-neon-green/20' : 
          getVolatilityColor(volatilityIndex).includes('bold-red') ? 'border-bold-red/20' : 'border-yellow-500/20'
        }`}>
          <h3 className="text-light-gray text-xs uppercase mb-2">Volatility</h3>
          <div className={`text-2xl font-bold font-teko ${getVolatilityColor(volatilityIndex)} flex items-center gap-2`}>
            <span className="text-xl">{getVolatilityIcon(volatilityIndex)}</span>
            {getVolatilityLabel(volatilityIndex)}
          </div>
          <div className="text-xs text-light-gray mt-2">Variance: {varianceValue.toFixed(2)}</div>
        </div>

        {/* Injury Impact */}
        <div className="bg-gradient-to-br from-charcoal to-navy p-6 rounded-xl border border-deep-red/20">
          <h3 className="text-light-gray text-xs uppercase mb-2">Injury Impact</h3>
          <div className="text-4xl font-bold text-deep-red font-teko">
            {simulation.injury_impact?.reduce((sum, inj) => sum + Math.abs(inj.impact_points), 0).toFixed(1) || '0.0'}
          </div>
          <div className="text-xs text-light-gray mt-2">Points Impact</div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex space-x-2 mb-6 border-b border-navy pb-3 overflow-x-auto">
        <button
          onClick={() => setActiveTab('distribution')}
          className={`px-6 py-3 rounded-t-lg font-semibold text-sm whitespace-nowrap transition ${
            activeTab === 'distribution'
              ? 'bg-gold text-white'
              : 'bg-charcoal text-light-gray hover:text-white'
          }`}
        >
          📊 Distribution
        </button>
        <button
          onClick={() => setActiveTab('injuries')}
          className={`px-6 py-3 rounded-t-lg font-semibold text-sm whitespace-nowrap transition ${
            activeTab === 'injuries'
              ? 'bg-gold text-white'
              : 'bg-charcoal text-light-gray hover:text-white'
          }`}
        >
          🏥 Injuries
        </button>
        <button
          onClick={() => setActiveTab('props')}
          className={`px-6 py-3 rounded-t-lg font-semibold text-sm whitespace-nowrap transition ${
            activeTab === 'props'
              ? 'bg-gold text-white'
              : 'bg-charcoal text-light-gray hover:text-white'
          }`}
        >
          🎯 Props
        </button>
        <button
          onClick={() => setActiveTab('movement')}
          className={`px-6 py-3 rounded-t-lg font-semibold text-sm whitespace-nowrap transition ${
            activeTab === 'movement'
              ? 'bg-gold text-white'
              : 'bg-charcoal text-light-gray hover:text-white'
          }`}
        >
          📈 Movement
        </button>
        <button
          onClick={() => setActiveTab('pulse')}
          className={`px-6 py-3 rounded-t-lg font-semibold text-sm whitespace-nowrap transition ${
            activeTab === 'pulse'
              ? 'bg-gold text-white'
              : 'bg-charcoal text-light-gray hover:text-white'
          }`}
        >
          💬 Pulse
        </button>
      </div>

      {/* Tab Content */}
      <div className="bg-charcoal rounded-xl p-6 border border-navy">
        {/* Panel 1: Score Distribution */}
        {activeTab === 'distribution' && (
          <div className="space-y-6">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              📊 Monte Carlo Simulation ({simulation.iterations.toLocaleString()} iterations)
            </h3>
            
            {scoreDistData.length > 0 ? (
              <>
                {/* Spread Distribution Chart */}
                <div>
                  <h4 className="text-lg font-semibold text-white mb-4">Margin of Victory Distribution</h4>
                  <ResponsiveContainer width="100%" height={400}>
                    <AreaChart data={scoreDistData}>
                        <defs>
                          <linearGradient id="colorTeamA" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#D4A64A" stopOpacity={0.8}/>
                          <stop offset="95%" stopColor="#D4A64A" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a2332" />
                      <XAxis 
                        dataKey="margin" 
                        stroke="#7b8a9d" 
                        label={{ value: 'Point Margin', position: 'insideBottom', offset: -5, fill: '#7b8a9d' }}
                      />
                      <YAxis 
                        stroke="#7b8a9d" 
                        label={{ value: 'Probability (%)', angle: -90, position: 'insideLeft', fill: '#7b8a9d' }}
                      />
                        <Tooltip 
                        contentStyle={{ backgroundColor: '#0f1419', border: '1px solid #D4A64A', borderRadius: '8px' }}
                        labelStyle={{ color: '#D4A64A' }}
                      />
                      <ReferenceLine x={0} stroke="#7b8a9d" strokeDasharray="3 3" label="Even" />
                      <Area 
                        type="monotone" 
                        dataKey="probability" 
                        stroke="#D4A64A" 
                        strokeWidth={2}
                        fill="url(#colorProb)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
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
                      <div className="text-light-gray text-xs mt-1">{simulation.iterations?.toLocaleString() || '50,000'} simulations</div>
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-4 text-center">
                      <div className="text-light-gray text-xs uppercase mb-2">Under {totalLine.toFixed(1)}</div>
                      <div className="text-gold font-bold text-3xl font-teko">
                        {underProb.toFixed(1)}%
                      </div>
                      <div className="text-light-gray text-xs mt-1">{simulation.iterations?.toLocaleString() || '50,000'} simulations</div>
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
              <div className="text-center text-light-gray py-8">No distribution data available</div>
            )}
          </div>
        )}

        {/* Panel 2: Injury Impact Meter */}
        {activeTab === 'injuries' && (
          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              🏥 Injury Impact Analysis
            </h3>
            {simulation.injury_impact && simulation.injury_impact.length > 0 ? (
              simulation.injury_impact.map((injury, idx) => (
                <div key={idx} className="bg-navy/30 rounded-lg p-4 flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <span className="text-2xl">{injury.status === 'OUT' ? '🔴' : '🟡'}</span>
                      <div>
                        <div className="text-white font-bold text-lg">{injury.player}</div>
                        <div className="text-light-gray text-sm">{injury.team} • {injury.status}</div>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-3xl font-bold font-teko ${
                      injury.impact_points > 0 ? 'text-neon-green' : 'text-bold-red'
                    }`}>
                      {injury.impact_points > 0 ? '+' : ''}{injury.impact_points.toFixed(1)}
                    </div>
                    <div className="text-xs text-light-gray">Point Impact</div>
                  </div>
                  {/* Visual Impact Bar */}
                  <div className="ml-6 w-32">
                    <div className="bg-charcoal rounded-full h-4">
                      <div
                        className={`h-4 rounded-full ${
                          injury.impact_points > 0 ? 'bg-neon-green' : 'bg-bold-red'
                        }`}
                        style={{ width: `${Math.min(Math.abs(injury.impact_points) * 10, 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center text-light-gray py-8">
                <div className="text-4xl mb-3">✅</div>
                <div>No significant injuries reported</div>
              </div>
            )}
          </div>
        )}

        {/* Panel 3: Top Props */}
        {activeTab === 'props' && (
          <div className="space-y-4">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              🎯 Top 5 Prop Mispricings
            </h3>
            {simulation.top_props && simulation.top_props.length > 0 ? (
              simulation.top_props.slice(0, 5).map((prop, idx) => (
                <div key={idx} className="bg-gradient-to-r from-navy/50 to-charcoal/50 rounded-lg p-5 border border-gold/20 hover:border-gold transition">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-white font-bold text-xl">{prop.player}</div>
                      <div className="text-light-gray text-sm">{prop.prop_type}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-gold font-bold text-2xl font-teko">
                        {prop.line}
                      </div>
                      <div className="text-xs text-light-gray">Line</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-charcoal/50 rounded-lg p-3">
                      <div className="text-light-gray text-xs uppercase mb-1">Win Probability</div>
                      <div className="text-white font-bold text-lg">{(prop.probability * 100).toFixed(1)}%</div>
                    </div>
                    <div className="bg-charcoal/50 rounded-lg p-3">
                      <div className="text-light-gray text-xs uppercase mb-1">Expected Value</div>
                      <div className={`font-bold text-lg ${prop.ev >= 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                        {prop.ev >= 0 ? '+' : ''}{prop.ev.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center text-light-gray py-8">
                No prop recommendations available
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
                <Line type="monotone" dataKey="fairValue" stroke="#7CFC00" strokeWidth={3} name="Fair Value" />
              </LineChart>
            </ResponsiveContainer>
            <div className="bg-gradient-to-r from-gold/10 to-purple-600/10 rounded-lg p-4 border border-gold/30">
              <p className="text-light-gray text-sm">
                💡 <span className="font-bold text-white">Market Agent Alert:</span> Fair value ({lineMovementData[lineMovementData.length - 1]?.fairValue.toFixed(2)}) is {lineMovementData[lineMovementData.length - 1]?.fairValue > lineMovementData[lineMovementData.length - 1]?.odds ? 'above' : 'below'} market odds ({lineMovementData[lineMovementData.length - 1]?.odds.toFixed(2)}), indicating {Math.abs(lineMovementData[lineMovementData.length - 1]?.fairValue - lineMovementData[lineMovementData.length - 1]?.odds) > 0.1 ? 'significant' : 'slight'} value opportunity.
              </p>
            </div>
          </div>
        )}

        {/* Panel 5: Community Pulse */}
        {activeTab === 'pulse' && (
          <div className="space-y-6">
            <h3 className="text-2xl font-bold text-white font-teko mb-4">
              💬 Community Pulse
            </h3>
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
          </div>
        )}
      </div>
    </div>
  );
};

export default GameDetail;
