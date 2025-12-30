import React from 'react';

interface ConfidenceTooltipProps {
  confidenceScore: number;
  volatility?: string;
  simCount?: number;
  tierLabel?: string;
}

/**
 * Confidence Score Tooltip - Explains what confidence means
 * 
 * CRITICAL: Confidence is NOT win probability
 * Confidence measures STABILITY of simulation outputs
 */
export const ConfidenceTooltip: React.FC<ConfidenceTooltipProps> = ({
  confidenceScore,
  volatility = 'MEDIUM',
  simCount = 10000,
  tierLabel = 'Starter'
}) => {
  const getConfidenceLabel = (score: number): string => {
    if (score >= 70) return 'High';
    if (score >= 40) return 'Medium';
    return 'Low';
  };

  const getConfidenceColor = (score: number): string => {
    if (score >= 70) return 'text-green-400';
    if (score >= 40) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const label = getConfidenceLabel(confidenceScore);
  const color = getConfidenceColor(confidenceScore);

  return (
    <div className="group relative inline-block">
      <div className={`flex items-center gap-1 cursor-help ${color}`}>
        <span className="font-semibold">{confidenceScore}/100</span>
        <span className="text-xs">({label})</span>
        <svg 
          className="w-4 h-4 opacity-70" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
          />
        </svg>
      </div>

      {/* Tooltip */}
      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-80 p-4 bg-gray-900 border border-gold/30 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
        <div className="text-sm text-gray-200 space-y-2">
          <div className="font-semibold text-lightGold border-b border-gold/20 pb-2">
            What is Confidence Score?
          </div>
          
          <p className="leading-relaxed">
            <strong>Confidence measures how stable the simulation output is.</strong>
          </p>
          
          <div className="space-y-1 text-xs">
            <div className="flex items-start gap-2">
              <span className="text-green-400">✓</span>
              <span><strong>Low variance</strong> + tight distribution = <strong>high confidence</strong></span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-orange-400">✗</span>
              <span><strong>High variance</strong> / coin-flip game = <strong>low confidence</strong></span>
            </div>
          </div>

          <div className="pt-2 border-t border-gray-700 text-xs space-y-1">
            <div><strong>Current Volatility:</strong> {volatility}</div>
            <div><strong>Simulation Tier:</strong> {tierLabel} ({simCount.toLocaleString()} iterations)</div>
          </div>

          <p className="text-xs italic text-gray-400 pt-2">
            Low confidence does not mean the model is wrong – it means the matchup is inherently swingy.
          </p>

          {simCount < 50000 && (
            <div className="pt-2 border-t border-purple-700/30 text-xs text-purple-300">
              💡 <strong>Pro tip:</strong> Higher tiers (50K-100K sims) provide tighter confidence bands.
            </div>
          )}
        </div>

        {/* Arrow */}
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-px">
          <div className="border-8 border-transparent border-t-gray-900"></div>
        </div>
      </div>
    </div>
  );
};

interface StrengthScoreTooltipProps {
  strengthScore: number;
}

/**
 * Strength Score Tooltip - Explains the 0-100 analytical score
 */
export const StrengthScoreTooltip: React.FC<StrengthScoreTooltipProps> = ({
  strengthScore
}) => {
  return (
    <div className="group relative inline-block">
      <div className="flex items-center gap-1 cursor-help">
        <span className="text-2xl font-bold bg-linear-to-r from-gold to-lightGold bg-clip-text text-transparent">
          {strengthScore}
        </span>
        <span className="text-sm text-gray-400">/ 100</span>
        <svg 
          className="w-4 h-4 text-gray-400 opacity-70" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
          />
        </svg>
      </div>

      {/* Tooltip */}
      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-72 p-4 bg-gray-900 border border-gold/30 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
        <div className="text-sm text-gray-200 space-y-2">
          <div className="font-semibold text-lightGold border-b border-gold/20 pb-2">
            Strength Score Explained
          </div>
          
          <p className="leading-relaxed text-xs">
            <strong>Strength Score</strong> = Probability × Expected Value × Correlation Stability (0–100)
          </p>
          
          <div className="space-y-1 text-xs">
            <div>• <strong>Higher scores</strong> indicate stronger analytical alignment</div>
            <div>• <strong>Combines</strong> win probability, EV, and leg synergy</div>
            <div>• <strong>Not a guarantee</strong> – analytical measure only</div>
          </div>

          <div className="pt-2 border-t border-gray-700 text-xs space-y-1">
            <div className="text-green-400">70+ = Strong alignment</div>
            <div className="text-yellow-400">40-69 = Moderate strength</div>
            <div className="text-orange-400">&lt;40 = Weak/risky</div>
          </div>

          <p className="text-xs italic text-gray-400 pt-2">
            This is an analytical score, not a betting recommendation.
          </p>
        </div>

        {/* Arrow */}
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-px">
          <div className="border-8 border-transparent border-t-gray-900"></div>
        </div>
      </div>
    </div>
  );
};

interface RiskGaugeProps {
  winProbability: number;  // 0.0 - 1.0
  label?: string;
}

/**
 * Risk Gauge with Corrected Thresholds
 * 
 * GREEN: 60%+ win probability
 * YELLOW: 45-59%
 * ORANGE: 30-44%
 * RED: <30%
 */
export const RiskGauge: React.FC<RiskGaugeProps> = ({
  winProbability,
  label
}) => {
  const percentage = Math.round(winProbability * 100);

  const getColorClasses = (prob: number): { bg: string; text: string; border: string } => {
    if (prob >= 0.60) {
      return {
        bg: 'bg-linear-to-r from-green-500/20 to-green-600/20',
        text: 'text-green-400',
        border: 'border-green-500/40'
      };
    } else if (prob >= 0.45) {
      return {
        bg: 'bg-linear-to-r from-yellow-500/20 to-yellow-600/20',
        text: 'text-yellow-400',
        border: 'border-yellow-500/40'
      };
    } else if (prob >= 0.30) {
      return {
        bg: 'bg-linear-to-r from-orange-500/20 to-orange-600/20',
        text: 'text-orange-400',
        border: 'border-orange-500/40'
      };
    } else {
      return {
        bg: 'bg-linear-to-r from-red-500/20 to-red-600/20',
        text: 'text-red-400',
        border: 'border-red-500/40'
      };
    }
  };

  const colors = getColorClasses(winProbability);

  const getRiskLabel = (prob: number): string => {
    if (prob >= 0.60) return 'Low Risk';
    if (prob >= 0.45) return 'Medium Risk';
    if (prob >= 0.30) return 'High Risk';
    return 'Very High Risk';
  };

  return (
    <div className={`p-3 rounded-lg border ${colors.bg} ${colors.border}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-300">
          {label || 'Risk Assessment'}
        </span>
        <span className={`text-sm font-bold ${colors.text}`}>
          {getRiskLabel(winProbability)}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${colors.text.replace('text-', 'bg-')}`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-gray-400">Win Probability</span>
        <span className={`text-lg font-bold ${colors.text}`}>
          {percentage}%
        </span>
      </div>
    </div>
  );
};
