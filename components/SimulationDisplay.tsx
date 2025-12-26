import React from 'react';
import { validateSimulationData } from '../utils/dataValidation';

export interface MonteCarloSimulation {
  simulation_id: string;
  event_id: string;
  iterations: number;
  team_a: string;
  team_b: string;
  team_a_win_probability: number;
  team_b_win_probability: number;
  avg_team_a_score: number;
  avg_team_b_score: number;
  avg_margin: number;
  volatility_index: number;
  confidence_score: number;
  spread_distribution?: Record<string, number>;
  total_distribution?: Record<string, number>;
  created_at: string;
  canonical_teams?: any; // Canonical team anchor
}

interface SimulationDisplayProps {
  simulation: MonteCarloSimulation;
  userTier: 'starter' | 'pro' | 'sharps_room' | 'founder';
}

const SimulationDisplay: React.FC<SimulationDisplayProps> = ({ simulation, userTier }) => {
  const hasAdvancedAccess = ['sharps_room', 'founder'].includes(userTier);
  const hasProAccess = ['pro', 'sharps_room', 'founder'].includes(userTier);

  const formatProbability = (prob: number) => (prob * 100).toFixed(2) + '%';
  const formatScore = (score: number) => score.toFixed(1);
  
  // Use canonical team data if available (prevents win probability flip bug)
  const canonicalTeams = simulation.canonical_teams;
  const team_a_win_prob = canonicalTeams?.home_team?.win_probability ?? simulation.team_a_win_probability;
  const team_b_win_prob = canonicalTeams?.away_team?.win_probability ?? simulation.team_b_win_probability;

  return (
    <div className="bg-charcoal rounded-xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold">Monte Carlo Simulation</h3>
          <p className="text-sm text-light-gray">
            {simulation.iterations.toLocaleString()} iterations
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className={`px-3 py-1 rounded-full text-xs font-semibold ${
            simulation.confidence_score > 0.75
              ? 'bg-neon-green/20 text-neon-green'
              : simulation.confidence_score > 0.5
              ? 'bg-electric-blue/20 text-electric-blue'
              : 'bg-gold/20 text-gold'
          }`}>
            {(simulation.confidence_score * 100).toFixed(0)}% confidence
          </div>
        </div>
      </div>

      {/* Win Probabilities */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-navy rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-light-gray">{simulation.team_a}</span>
            <span className="text-2xl font-bold text-electric-blue">
              {formatProbability(team_a_win_prob)}
            </span>
          </div>
          <div className="h-2 bg-charcoal rounded-full overflow-hidden">
            <div
              className="h-full bg-electric-blue transition-all"
              style={{ width: `${team_a_win_prob * 100}%` }}
            />
          </div>
          <div className="text-sm text-light-gray">
            Avg Score: {formatScore(simulation.avg_team_a_score)}
          </div>
        </div>

        <div className="bg-navy rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-light-gray">{simulation.team_b}</span>
            <span className="text-2xl font-bold text-bold-red">
              {formatProbability(team_b_win_prob)}
            </span>
          </div>
          <div className="h-2 bg-charcoal rounded-full overflow-hidden">
            <div
              className="h-full bg-bold-red transition-all"
              style={{ width: `${team_b_win_prob * 100}%` }}
            />
          </div>
          <div className="text-sm text-light-gray">
            Avg Score: {formatScore(simulation.avg_team_b_score)}
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-navy rounded-lg p-3 text-center">
          <div className="text-sm text-light-gray mb-1">Avg Margin</div>
          <div className="text-xl font-bold">
            {simulation.avg_margin > 0 ? '+' : ''}{formatScore(simulation.avg_margin)}
          </div>
        </div>
        <div className="bg-navy rounded-lg p-3 text-center">
          <div className="text-sm text-light-gray mb-1">Volatility</div>
          <div className="text-xl font-bold text-gold">
            {formatScore(simulation.volatility_index)}
          </div>
        </div>
        <div className="bg-navy rounded-lg p-3 text-center">
          <div className="text-sm text-light-gray mb-1">Total Points</div>
          <div className="text-xl font-bold">
            {formatScore(simulation.avg_team_a_score + simulation.avg_team_b_score)}
          </div>
        </div>
        <div className="bg-navy rounded-lg p-3 text-center">
          <div className="text-sm text-light-gray mb-1">Confidence</div>
          <div className="text-xl font-bold text-neon-green">
            {(simulation.confidence_score * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* Spread Distribution - Pro+ */}
      {hasProAccess && simulation.spread_distribution && (
        <div className="space-y-3">
          <h4 className="font-semibold text-sm">Spread Coverage Probability</h4>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
            {Object.entries(simulation.spread_distribution)
              .slice(0, 12)
              .map(([spread, probability]) => (
                <div key={spread} className="bg-navy rounded p-2 text-center">
                  <div className="text-xs text-light-gray">{spread.replace('spread_', '')}</div>
                  <div className="text-sm font-bold">{(Number(probability) * 100).toFixed(1)}%</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Total Distribution - Pro+ */}
      {hasProAccess && simulation.total_distribution && (
        <div className="space-y-3">
          <h4 className="font-semibold text-sm">Over/Under Probability</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(simulation.total_distribution)
              .slice(0, 8)
              .map(([total, probability]) => (
                <div key={total} className="bg-navy rounded p-2 text-center">
                  <div className="text-xs text-light-gray">{total.replace('total_', '').toUpperCase()}</div>
                  <div className="text-sm font-bold">{(Number(probability) * 100).toFixed(1)}%</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Upgrade CTA for Starter users */}
      {!hasProAccess && (
        <div className="bg-electric-blue/10 border border-electric-blue rounded-lg p-4 text-center">
          <p className="text-sm text-light-gray mb-2">
            Unlock spread distributions and totals analysis
          </p>
          <button className="bg-electric-blue text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-electric-blue/90 transition">
            Upgrade to Pro
          </button>
        </div>
      )}

      {/* Advanced Analytics - Sharps Room only */}
      {hasAdvancedAccess && (
        <div className="border-t border-navy pt-4">
          <div className="flex items-center justify-between text-xs text-light-gray">
            <span>Simulation ID: {simulation.simulation_id}</span>
            <span>{new Date(simulation.created_at).toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default SimulationDisplay;
