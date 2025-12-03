import React from 'react';

interface LegalDisclaimerProps {
  variant?: 'full' | 'compact';
  className?: string;
}

/**
 * LegalDisclaimer - Standardized disclaimer component
 * 
 * Official wording per V1 Production spec:
 * "MODEL MISPRICING — NOT a betting recommendation."
 */
export default function LegalDisclaimer({ 
  variant = 'full', 
  className = '' 
}: LegalDisclaimerProps) {
  
  if (variant === 'compact') {
    return (
      <div className={`text-[10px] text-gray-500 italic ${className}`}>
        MODEL MISPRICING — NOT a betting recommendation.
      </div>
    );
  }
  
  return (
    <div className={`bg-gray-900/50 border border-gray-700/50 rounded-lg p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <span className="text-yellow-500 text-xl flex-shrink-0">⚠️</span>
        <div>
          <div className="text-yellow-500 font-bold text-sm mb-2">
            MODEL MISPRICING — NOT a betting recommendation
          </div>
          <div className="text-gray-400 text-xs leading-relaxed">
            BeatVegas identifies statistical deviations between our simulation output and sportsbook odds.
            No part of this output constitutes financial or betting advice.
          </div>
        </div>
      </div>
    </div>
  );
}
