import React, { useState } from 'react';
import type { PropMispricing } from '../types';

interface PropCardProps {
  prop: PropMispricing;
  rank: number; // Display ranking (1-5 for Top 5)
  onViewAnalysis?: (prop: PropMispricing) => void;
  onCompare?: (prop: PropMispricing) => void;
  onLogDecision?: (prop: PropMispricing) => void;
}

const PropCard: React.FC<PropCardProps> = ({ 
  prop, 
  rank,
  onViewAnalysis,
  onCompare,
  onLogDecision 
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getEVColor = (ev: number) => {
    if (ev >= 5) return 'text-neon-green';
    if (ev >= 2) return 'text-vibrant-yellow';
    return 'text-white';
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.75) return 'bg-neon-green';
    if (confidence >= 0.6) return 'bg-vibrant-yellow';
    return 'bg-electric-blue';
  };

  // Calculate confidence level (HIGH/MEDIUM/LOW)
  const getConfidenceLevel = (confidence: number): string => {
    if (confidence >= 0.75) return 'HIGH';
    if (confidence >= 0.60) return 'MEDIUM';
    return 'LOW';
  };

  const getConfidenceBadgeColor = (level: string): string => {
    switch (level) {
      case 'HIGH': return 'bg-neon-green/20 text-neon-green border-neon-green';
      case 'MEDIUM': return 'bg-vibrant-yellow/20 text-vibrant-yellow border-vibrant-yellow';
      case 'LOW': return 'bg-electric-blue/20 text-electric-blue border-electric-blue';
      default: return 'bg-navy text-white border-navy';
    }
  };

  // Calculate volatility based on confidence range width
  const getVolatilityLevel = (): string => {
    if (!prop.confidence_range) return 'UNKNOWN';
    const range = prop.confidence_range[1] - prop.confidence_range[0];
    const linePercent = (range / prop.line) * 100;
    
    if (linePercent <= 20) return 'LOW';
    if (linePercent <= 40) return 'MEDIUM';
    return 'HIGH';
  };

  const getVolatilityBadgeColor = (level: string): string => {
    switch (level) {
      case 'LOW': return 'bg-neon-green/20 text-neon-green border-neon-green';
      case 'MEDIUM': return 'bg-vibrant-yellow/20 text-vibrant-yellow border-vibrant-yellow';
      case 'HIGH': return 'bg-bold-red/20 text-bold-red border-bold-red';
      default: return 'bg-navy text-white border-navy';
    }
  };

  const winProbPercentage = Math.round(prop.win_probability * 100);
  const evFormatted = prop.expected_value >= 0 ? `+${prop.expected_value.toFixed(2)}%` : `${prop.expected_value.toFixed(2)}%`;
  const confidenceLevel = getConfidenceLevel(prop.confidence);
  const volatilityLevel = getVolatilityLevel();

  // Generate mini trend chart data (if recent performance data available)
  const trendData = prop.recent_avg && prop.season_avg ? [
    prop.season_avg * 0.85,
    prop.season_avg * 0.92,
    prop.season_avg * 1.05,
    prop.season_avg * 0.98,
    prop.recent_avg
  ] : null;

  const renderMiniChart = () => {
    if (!trendData) return null;
    
    const max = Math.max(...trendData);
    const min = Math.min(...trendData);
    const range = max - min || 1;
    
    return (
      <div className="flex items-end space-x-1 h-8">
        {trendData.map((value, idx) => {
          const height = ((value - min) / range) * 100;
          const isLast = idx === trendData.length - 1;
          return (
            <div
              key={idx}
              className={`flex-1 rounded-t ${isLast ? 'bg-electric-blue' : 'bg-navy'}`}
              style={{ height: `${Math.max(height, 10)}%` }}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div className="bg-charcoal rounded-lg border border-navy hover:border-electric-blue transition-all duration-300 overflow-hidden">
      {/* Main Card Content */}
      <div className="p-5">
        {/* Top Row: Rank Badge + BeatVegas Edge Branding */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="bg-electric-blue/20 text-electric-blue text-xs font-bold px-3 py-1 rounded-full">
              #{rank} PROP
            </div>
            <div className="bg-gradient-to-r from-neon-green/20 to-electric-blue/20 text-white text-xs font-bold px-3 py-1 rounded-full border border-neon-green/30">
              ⚡ BEATVEGAS EDGE™
            </div>
          </div>
          <button 
            className="text-light-gray hover:text-white transition-colors"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <svg 
              className={`w-5 h-5 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              xmlns="http://www.w3.org/2000/svg" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Player Name & Market */}
        <div className="mb-2">
          <h3 className="text-xl font-bold text-white font-teko leading-tight">
            {prop.player_name} — {prop.market}
          </h3>
        </div>

        {/* Team & Position */}
        <div className="flex items-center space-x-2 mb-4">
          <span className="text-sm text-light-gray">{prop.team}</span>
          <span className="text-light-gray">·</span>
          <span className="text-sm font-semibold text-electric-blue">{prop.position}</span>
        </div>

        {/* Intelligence Indicators: Confidence + Volatility + Model Edge */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="text-center">
            <p className="text-[10px] text-light-gray uppercase mb-1">Confidence</p>
            <div className={`px-2 py-1 rounded border text-xs font-bold ${getConfidenceBadgeColor(confidenceLevel)}`}>
              {confidenceLevel}
            </div>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-light-gray uppercase mb-1">Volatility</p>
            <div className={`px-2 py-1 rounded border text-xs font-bold ${getVolatilityBadgeColor(volatilityLevel)}`}>
              {volatilityLevel}
            </div>
          </div>
          <div className="text-center">
            <p className="text-[10px] text-light-gray uppercase mb-1">Model Edge</p>
            <div className="px-2 py-1 rounded border border-neon-green/30 bg-neon-green/10 text-neon-green text-xs font-bold">
              +{prop.expected_value.toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Line */}
        <div className="mb-3">
          <p className="text-xs text-light-gray font-semibold mb-1">LINE</p>
          <p className="text-3xl font-bold text-white font-teko">{prop.line}</p>
        </div>

        {/* Win Probability Bar */}
        <div className="mb-3">
          <p className="text-xs text-light-gray font-semibold mb-1">WIN PROBABILITY</p>
          <div className="flex items-center space-x-3">
            <div className="flex-1 bg-navy rounded-full h-3 relative overflow-hidden">
              <div
                className={`h-3 rounded-full ${getConfidenceColor(prop.win_probability)} transition-all duration-500`}
                style={{ width: `${winProbPercentage}%` }}
              ></div>
            </div>
            <span className="text-lg font-bold text-white w-14 text-right">{winProbPercentage}%</span>
          </div>
        </div>

        {/* Expected Value */}
        <div className="mb-3">
          <p className="text-xs text-light-gray font-semibold mb-1">EXPECTED VALUE</p>
          <p className={`text-2xl font-bold ${getEVColor(prop.expected_value)} font-teko`}>
            {evFormatted}
          </p>
        </div>

        {/* Mini Trend Chart */}
        {trendData && (
          <div className="mb-4 p-3 bg-navy/30 rounded">
            <p className="text-xs text-light-gray font-semibold mb-2">LAST 5 GAMES TREND</p>
            {renderMiniChart()}
            <div className="flex justify-between text-[10px] text-light-gray mt-1">
              <span>G-5</span>
              <span>Recent: {prop.recent_avg?.toFixed(1)}</span>
            </div>
          </div>
        )}

        {/* Quick Stats */}
        {(prop.recent_avg || prop.season_avg) && (
          <div className="pt-3 border-t border-navy grid grid-cols-2 gap-3 text-sm mb-4">
            {prop.recent_avg && (
              <div>
                <p className="text-xs text-light-gray">Last 5 Avg</p>
                <p className="font-semibold text-white">{prop.recent_avg.toFixed(1)}</p>
              </div>
            )}
            {prop.season_avg && (
              <div>
                <p className="text-xs text-light-gray">Season Avg</p>
                <p className="font-semibold text-white">{prop.season_avg.toFixed(1)}</p>
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => onViewAnalysis?.(prop)}
            className="bg-electric-blue/10 hover:bg-electric-blue/20 border border-electric-blue/30 text-electric-blue text-xs font-semibold py-2 px-2 rounded transition-colors"
          >
            View Analysis
          </button>
          <button
            onClick={() => onCompare?.(prop)}
            className="bg-vibrant-yellow/10 hover:bg-vibrant-yellow/20 border border-vibrant-yellow/30 text-vibrant-yellow text-xs font-semibold py-2 px-2 rounded transition-colors"
          >
            Compare
          </button>
          <button
            onClick={() => onLogDecision?.(prop)}
            className="bg-neon-green/10 hover:bg-neon-green/20 border border-neon-green/30 text-neon-green text-xs font-semibold py-2 px-2 rounded transition-colors"
          >
            Log Decision
          </button>
        </div>

        {/* Expand Indicator */}
        <div className="mt-3 text-center">
          <span className="text-xs text-light-gray italic">
            {isExpanded ? 'Click arrow to collapse' : 'Click arrow for full analysis'}
          </span>
        </div>
      </div>

      {/* Expanded Details Panel */}
      {isExpanded && (
        <div className="bg-navy/30 p-5 border-t border-navy space-y-5 animate-slideDown">
          {/* Performance Context */}
          <div>
            <h4 className="text-sm font-bold text-white mb-3 flex items-center space-x-2">
              <svg className="w-4 h-4 text-electric-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span>PERFORMANCE CONTEXT</span>
            </h4>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {prop.recent_avg && (
                <div className="bg-charcoal/50 p-3 rounded">
                  <p className="text-xs text-light-gray mb-1">Last 5 Games</p>
                  <p className="text-lg font-bold text-white">{prop.recent_avg.toFixed(1)}</p>
                </div>
              )}
              {prop.season_avg && (
                <div className="bg-charcoal/50 p-3 rounded">
                  <p className="text-xs text-light-gray mb-1">Season Average</p>
                  <p className="text-lg font-bold text-white">{prop.season_avg.toFixed(1)}</p>
                </div>
              )}
              {prop.minutes_projection && (
                <div className="bg-charcoal/50 p-3 rounded">
                  <p className="text-xs text-light-gray mb-1">Proj. Minutes</p>
                  <p className="text-lg font-bold text-white">{prop.minutes_projection}</p>
                </div>
              )}
              {prop.opponent_rank && (
                <div className="bg-charcoal/50 p-3 rounded">
                  <p className="text-xs text-light-gray mb-1">Opp. Defense Rank</p>
                  <p className="text-lg font-bold text-white">#{prop.opponent_rank}</p>
                </div>
              )}
            </div>
          </div>

          {/* Simulation Distribution */}
          {prop.distribution && prop.distribution.length > 0 && (
            <div>
              <h4 className="text-sm font-bold text-white mb-3 flex items-center space-x-2">
                <svg className="w-4 h-4 text-electric-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                </svg>
                <span>SIMULATION DISTRIBUTION</span>
              </h4>
              <div className="bg-charcoal/50 p-4 rounded space-y-2">
                {prop.distribution.slice(0, 5).map((point, idx) => (
                  <div key={idx} className="flex items-center space-x-3">
                    <span className="text-xs text-light-gray w-12">{point.value.toFixed(1)}</span>
                    <div className="flex-1 bg-navy rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-electric-blue h-2 rounded-full"
                        style={{ width: `${point.probability * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-white w-14 text-right">
                      {(point.probability * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confidence Range */}
          {prop.confidence_range && (
            <div>
              <h4 className="text-sm font-bold text-white mb-3 flex items-center space-x-2">
                <svg className="w-4 h-4 text-electric-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>95% CONFIDENCE INTERVAL</span>
              </h4>
              <div className="bg-charcoal/50 p-4 rounded">
                <p className="text-sm text-light-gray text-center">
                  Projected range: <span className="text-white font-bold">{prop.confidence_range[0].toFixed(1)}</span>
                  {' '}-{' '}
                  <span className="text-white font-bold">{prop.confidence_range[1].toFixed(1)}</span>
                </p>
              </div>
            </div>
          )}

          {/* Scenario Factors */}
          {prop.scenario_factors && prop.scenario_factors.length > 0 && (
            <div>
              <h4 className="text-sm font-bold text-white mb-3 flex items-center space-x-2">
                <svg className="w-4 h-4 text-electric-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <span>KEY FACTORS</span>
              </h4>
              <div className="space-y-2">
                {prop.scenario_factors.map((factor, idx) => (
                  <div key={idx} className="flex items-start space-x-2 text-sm">
                    <span className="text-electric-blue mt-0.5">•</span>
                    <span className="text-light-gray">{factor}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Decision Intelligence Footer */}
          <div className="pt-4 border-t border-navy">
            <p className="text-xs text-light-gray italic text-center">
              This analysis provides quantified edge for informed decision-making.
              <br />
              All projections are analytical insights, not guaranteed outcomes.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default PropCard;
