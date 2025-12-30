import React from 'react';
import SimulationBadge from './SimulationBadge';
import ConfidenceGauge from './ConfidenceGauge';
import { getConfidenceTier, getConfidenceGlow } from '../utils/confidenceTiers';
import { getSportLabels } from '../utils/sportLabels';

interface FirstHalfAnalysisProps {
  eventId: string;
  simulation: {
    projected_total: number;
    bookmaker_line?: number;  // Actual bookmaker 1H line
    book_line_available?: boolean;
    bookmaker_source?: string;  // e.g., "DraftKings"
    over_probability: number;
    under_probability: number;
    confidence: number;
    pace_factor: number;
    reasoning: string;
    iterations: number;
    sport_key?: string; // NEW: Sport key for terminology
    metadata?: {
      user_tier?: string;
      iterations_run?: number;
      precision_level?: string;
    };
  } | null;
  loading: boolean;
  sportKey?: string; // NEW: Accept sport_key as prop
}

const FirstHalfAnalysis: React.FC<FirstHalfAnalysisProps> = ({ eventId, simulation, loading, sportKey }) => {
  if (loading) {
    return (
      <div className="bg-charcoal rounded-xl p-6 border border-navy">
        <div className="animate-pulse">
          <div className="h-6 bg-navy rounded w-1/3 mb-4"></div>
          <div className="h-20 bg-navy rounded"></div>
        </div>
      </div>
    );
  }

  if (!simulation) {
    return (
      <div className="bg-charcoal rounded-xl p-6 border border-navy text-center">
        <p className="text-light-gray">First Half analysis not available</p>
      </div>
    );
  }

  const { projected_total, bookmaker_line, book_line_available = false, bookmaker_source, over_probability, under_probability, confidence, pace_factor, reasoning, iterations } = simulation;
  
  // Calculate distribution if backend didn't provide it
  // If both are 0, it means backend didn't calculate distribution
  const hasValidDistribution = (over_probability > 0 || under_probability > 0);
  
  // If no valid distribution, estimate from projected total vs line
  let calculatedOver = over_probability;
  let calculatedUnder = under_probability;
  
  if (!hasValidDistribution) {
    const referenceLine = bookmaker_line || Math.round(projected_total * 2) / 2;
    const difference = projected_total - referenceLine;
    
    // Simple logistic curve estimation
    // If projected is 5+ points above line, model strongly favors Over
    if (difference > 5) {
      calculatedOver = 0.70 + Math.min(0.20, difference / 50);
      calculatedUnder = 1 - calculatedOver;
    } else if (difference < -5) {
      calculatedUnder = 0.70 + Math.min(0.20, Math.abs(difference) / 50);
      calculatedOver = 1 - calculatedUnder;
    } else {
      // Close to line - use 55/45 split based on direction
      calculatedOver = 0.50 + (difference / 20);
      calculatedUnder = 1 - calculatedOver;
    }
  }
  
  // Determine sport type and get appropriate labels
  const activeSportKey = sportKey || simulation.sport_key || '';
  const sportLabels = getSportLabels(activeSportKey);
  
  // Use bookmaker line if available, otherwise use projected total
  const referenceLine = bookmaker_line || Math.round(projected_total * 2) / 2;
  
  // Determine recommended side (Over or Under)
  const recommendedSide = calculatedOver > calculatedUnder ? "OVER" : "UNDER";
  const recommendedProb = calculatedOver > calculatedUnder ? calculatedOver : calculatedUnder;
  
  // Use universal confidence tier
  const confidencePercent = confidence * 100;
  const confidenceTier = getConfidenceTier(confidencePercent);

  // Tempo analysis based on pace factor
  const getTempoLabel = (pace: number) => {
    if (pace > 1.03) return { label: "Above Average Tempo (Model Attribute)", icon: "📊", color: "text-electric-blue" };
    if (pace < 0.98) return { label: "Below Average Tempo (Model Attribute)", icon: "📊", color: "text-electric-blue" };
    return { label: "Average Tempo (Model Attribute)", icon: "📊", color: "text-electric-blue" };
  };

  const tempo = getTempoLabel(pace_factor);

  return (
    <div className="bg-charcoal rounded-xl p-6 border border-navy animate-fade-in mt-8">
      {/* Header with Simulation Badge - Extra Spacing */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-3xl font-bold text-white font-teko">
          {sportLabels.headerEmoji} {sportLabels.headerTitle}
        </h3>
        <div 
          className="text-xs font-bold px-4 py-2 rounded-full"
          style={{
            backgroundColor: confidenceTier.bgColor,
            color: confidenceTier.textColor,
            borderWidth: '1px',
            borderColor: confidenceTier.borderColor
          }}
        >
          {confidenceTier.label}
        </div>
      </div>

      {/* Simulation Power Badge */}
      <div className="mb-6 flex items-center justify-between">
        <div className="bg-navy/80 border border-gold/30 rounded-lg px-4 py-2">
          <SimulationBadge 
            tier={(simulation.metadata?.user_tier as any) || 'free'} 
            simulationCount={iterations}
            showUpgradeHint={false}
          />
        </div>
        <ConfidenceGauge 
          confidence={confidence * 100}
          size="sm"
          animated={true}
        />
      </div>

      {/* Main Model Output */}
      <div className="bg-navy rounded-lg p-6 mb-6">
        <div className="text-center">
          <div className="text-light-gray text-sm mb-2">
            {book_line_available ? `${bookmaker_source || 'BOOKMAKER'} 1H LINE` : 'MODEL MEDIAN PROJECTION'}
          </div>
          <div className="text-4xl font-bold text-electric-blue mb-2">
            {referenceLine.toFixed(1)} points
          </div>
          <div className="text-light-gray text-sm mt-2">
            Model Distribution: {(calculatedOver * 100).toFixed(1)}% above / {(calculatedUnder * 100).toFixed(1)}% below {referenceLine.toFixed(1)}
          </div>
          {book_line_available && (
            <div className="mt-3 text-xs text-green-400 bg-charcoal/50 rounded px-3 py-1.5 inline-block">
              ✅ {bookmaker_source} 1H line — probabilities vs actual book line
            </div>
          )}
          {!book_line_available && (
            <>
              <div className="mt-3 text-xs text-yellow-400 bg-charcoal/50 rounded px-3 py-1.5 inline-block">
                📊 No bookmaker 1H line available — showing model projection only
              </div>
              <div className="mt-2 text-xs text-gold font-semibold bg-gold/10 border border-gold/30 rounded px-3 py-1.5 inline-block">
                ⚠️ 1H model accuracy is reduced when no market anchor exists
              </div>
              <div className="mt-2 text-xs text-electric-blue">
                Projected CLV: +0.0 pts
              </div>
            </>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Projected Total */}
        <div className="bg-navy rounded-lg p-4">
          <div className="text-light-gray text-xs mb-1">PROJECTED 1H TOTAL</div>
          <div className="text-white text-2xl font-bold">{projected_total.toFixed(1)}</div>
        </div>

        {/* Sim Power */}
        <div className="bg-navy rounded-lg p-4">
          <div className="text-light-gray text-xs mb-1">SIM POWER</div>
          <div className="text-white text-xl font-bold">{(iterations / 1000).toFixed(0)}K</div>
          <div className="text-light-gray text-xs">1H Scenarios</div>
        </div>

        {/* Tempo */}
        <div className="bg-navy rounded-lg p-4">
          <div className="text-light-gray text-xs mb-1">{sportLabels.paceLabel.toUpperCase()} ANALYSIS</div>
          <div className={`${tempo.color} text-lg font-semibold flex items-center`}>
            <span className="mr-2">{tempo.icon}</span>
            {tempo.label}
          </div>
        </div>
      </div>

      {/* Model Distribution Breakdown - Enhanced Visual Contrast */}
      <div className="mb-6">
        <div className="text-center text-sm text-light-gray mb-3 font-semibold">Model Distribution Analysis</div>
        <div className="flex justify-between text-sm font-bold mb-2">
          <span className="text-neon-green flex items-center gap-1">
            <span className="text-lg">📈</span>
            Above {referenceLine.toFixed(1)}
          </span>
          <span className="text-neon-green text-lg">{(calculatedOver * 100).toFixed(1)}%</span>
        </div>
        <div className="h-6 bg-charcoal rounded-full overflow-hidden flex border-2 border-gold/40 shadow-lg">
          <div
            className="bg-linear-to-r from-neon-green to-green-400 h-full transition-all duration-500 relative"
            style={{ width: `${calculatedOver * 100}%` }}
          >
            <div className="absolute inset-0 bg-neon-green/20 animate-pulse"></div>
          </div>
          <div
            className="bg-linear-to-r from-purple-600 to-purple-400 h-full transition-all duration-500 relative"
            style={{ width: `${calculatedUnder * 100}%` }}
          >
            <div className="absolute inset-0 bg-purple-400/20 animate-pulse"></div>
          </div>
        </div>
        <div className="flex justify-between text-sm font-bold mt-2">
          <span className="text-purple-300 flex items-center gap-1">
            <span className="text-lg">📉</span>
            Below {referenceLine.toFixed(1)}
          </span>
          <span className="text-purple-300 text-lg">{(calculatedUnder * 100).toFixed(1)}%</span>
        </div>
        
        {/* Fix #5: Add description under distribution bar */}
        <div className="text-center text-xs text-light-gray/70 mt-3">
          {Math.abs(calculatedOver - calculatedUnder) < 0.1 
            ? 'Model expects a near-even distribution in the first half.'
            : calculatedOver > calculatedUnder
              ? `Model projects ${((calculatedOver - 0.5) * 200).toFixed(0)}% higher scoring than median.`
              : `Model projects ${((calculatedUnder - 0.5) * 200).toFixed(0)}% lower scoring than median.`
          }
        </div>
      </div>

      {/* Reasoning */}
      <div className="bg-navy rounded-lg p-4">
        <div className="text-light-gray text-xs font-semibold mb-2">AI REASONING</div>
        <div className="text-white text-sm leading-relaxed">
          {reasoning}
        </div>
      </div>

      {/* 1H Physics Callout */}
      <div className="mt-4 bg-electric-blue/10 border border-electric-blue rounded-lg p-4">
        <div className="flex items-start">
          <span className="text-2xl mr-3">⚙️</span>
          <div>
            <div className="text-electric-blue font-semibold text-sm mb-1">
              1H SIMULATION PHYSICS
            </div>
            <div className="text-light-gray text-xs">
              • {sportLabels.physicsDistribution}<br />
              • {sportLabels.physicsMinutes}<br />
              • {sportLabels.physicsFatigue}<br />
              • 50% Game Duration ({sportLabels.durationLabel})
            </div>
          </div>
        </div>
      </div>

      {/* Interpretation Notice */}
      <div className="mt-4 bg-gold/5 border border-gold/20 rounded-lg p-3 text-center">
        <p className="text-xs text-light-gray">
          <span className="text-gold font-semibold">Statistical Model Output</span> — Use as part of your decision framework.
        </p>
      </div>
    </div>
  );
};

export default FirstHalfAnalysis;
