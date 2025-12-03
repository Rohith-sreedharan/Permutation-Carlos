import React, { useEffect, useState } from 'react';
import { getGaugeColor, getConfidenceTier } from '../utils/confidenceTiers';

interface ConfidenceGaugeProps {
  confidence: number;  // 0-100
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  animated?: boolean;
  className?: string;
}

/**
 * ConfidenceGauge - Circular progress indicator for confidence levels
 * Provides visual certainty with smooth animations
 */
export default function ConfidenceGauge({ 
  confidence, 
  size = 'md',
  showLabel = true,
  animated = true,
  className = '' 
}: ConfidenceGaugeProps) {
  const [displayConfidence, setDisplayConfidence] = useState(animated ? 0 : confidence);

  // Animate on mount
  useEffect(() => {
    if (animated) {
      const timer = setTimeout(() => {
        setDisplayConfidence(confidence);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [confidence, animated]);

  // Size configurations
  const sizeConfig = {
    sm: { diameter: 48, stroke: 4, fontSize: 'text-xs' },
    md: { diameter: 64, stroke: 5, fontSize: 'text-sm' },
    lg: { diameter: 96, stroke: 6, fontSize: 'text-lg' },
  }[size];

  const { diameter, stroke } = sizeConfig;
  const radius = (diameter - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (displayConfidence / 100) * circumference;

  // Use universal confidence tier color
  const color = getGaugeColor(confidence);

  return (
    <div className={`inline-flex flex-col items-center gap-1 ${className}`}>
      <div className="relative" style={{ width: diameter, height: diameter }}>
        {/* Background circle */}
        <svg
          width={diameter}
          height={diameter}
          className="transform -rotate-90"
        >
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            fill="none"
            stroke="#E5E7EB"
            strokeWidth={stroke}
          />
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{
              transition: animated ? 'stroke-dashoffset 0.8s ease-out' : 'none',
            }}
          />
        </svg>
        
        {/* Center text */}
        <div 
          className="absolute inset-0 flex items-center justify-center"
        >
          <span 
            className={`font-bold ${sizeConfig.fontSize}`}
            style={{ color }}
          >
            {Math.round(displayConfidence)}
          </span>
        </div>
      </div>

      {showLabel && (
        <span className="text-xs text-gray-400 font-medium">
          Stability
        </span>
      )}
    </div>
  );
}
