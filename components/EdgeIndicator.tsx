import React, { useState } from 'react';

interface EdgeIndicatorProps {
  edge: number;
  className?: string;
}

/**
 * EdgeIndicator - Small amber tag for model-market discrepancies
 * 
 * Premium, subtle indicator that protects legally without hurting UX
 * Appears as small tag with tooltip explaining the statistical nature
 */
export default function EdgeIndicator({ edge, className = '' }: EdgeIndicatorProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div 
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Small Amber Tag */}
      <div className="flex items-center gap-1 bg-gold/10 border border-gold/40 rounded px-2 py-0.5">
        <span className="text-gold text-xs">🔶</span>
        <span className="text-gold text-xs font-semibold">
          {edge > 0 ? '+' : ''}{edge.toFixed(1)} Edge
        </span>
      </div>
      
      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 w-64 p-3 bg-navy/95 border border-gold/30 rounded-lg shadow-2xl z-50">
          <div className="text-xs text-light-gray leading-relaxed">
            <div className="text-gold font-semibold mb-1">Model–Market Discrepancy Indicator</div>
            <div>
              Statistical output only. Not a betting recommendation. This shows the pricing difference between our simulation output and the sportsbook line.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
