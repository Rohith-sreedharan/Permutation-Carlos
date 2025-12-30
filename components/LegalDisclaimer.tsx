import React from 'react';

interface LegalDisclaimerProps {
  variant?: 'full' | 'compact';
  className?: string;
}

/**
 * LegalDisclaimer - Institutional-grade interpretation notice
 * 
 * Frames data as statistical model output, not betting advice
 * Builds confidence while maintaining legal protection
 */
export default function LegalDisclaimer({ 
  variant = 'full', 
  className = '' 
}: LegalDisclaimerProps) {
  
  if (variant === 'compact') {
    return (
      <div className={`text-[10px] text-gray-400 italic ${className}`}>
        Statistical output only. Not a betting recommendation.
      </div>
    );
  }
  
  return (
    <div className={`bg-gold/5 border border-gold/20 rounded-lg p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <span className="text-gold text-lg shrink-0">🔶</span>
        <div>
          <div className="text-gold font-bold text-sm mb-2">
            Institutional-Grade Interpretation Notice
          </div>
          <div className="text-light-gray text-xs leading-relaxed">
            This platform provides statistical model outputs. Edges represent pricing discrepancies between our simulations and the sportsbook line — not guaranteed outcomes. Use these insights as part of your decision framework.
          </div>
        </div>
      </div>
    </div>
  );
}
