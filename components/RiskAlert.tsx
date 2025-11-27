import React from 'react';

interface RiskAlertProps {
  isOpen: boolean;
  onClose: () => void;
  betCount: number;
  timeframe: string;
  unitSize: number;
  recommendedAction: string;
}

const RiskAlert: React.FC<RiskAlertProps> = ({ 
  isOpen, 
  onClose, 
  betCount, 
  timeframe, 
  unitSize,
  recommendedAction 
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-navy border-2 border-bold-red rounded-xl p-8 max-w-md w-full mx-4 shadow-2xl animate-pulse-slow">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="text-6xl mb-4">⚠️</div>
          <h2 className="text-3xl font-bold text-bold-red mb-2">Tilt Alert</h2>
          <p className="text-light-gray">
            Responsible Gaming Protection Activated
          </p>
        </div>

        {/* Warning Content */}
        <div className="bg-charcoal rounded-lg p-6 mb-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-light-gray">Bets Placed:</span>
            <span className="text-xl font-bold text-bold-red">{betCount} bets</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-light-gray">In Timeframe:</span>
            <span className="text-white font-semibold">{timeframe}</span>
          </div>
          <div className="border-t border-navy pt-4">
            <div className="text-sm text-light-gray mb-2">Your Unit Size</div>
            <div className="text-2xl font-bold text-white">${unitSize.toFixed(2)}</div>
            <div className="text-xs text-light-gray mt-1">
              Stick to your strategy - don't chase losses
            </div>
          </div>
        </div>

        {/* Recommended Action */}
        <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <span className="text-2xl">💡</span>
            <div>
              <div className="font-semibold text-yellow-500 mb-1">Recommendation</div>
              <p className="text-sm text-white">{recommendedAction}</p>
            </div>
          </div>
        </div>

        {/* Responsible Gaming Tips */}
        <div className="space-y-3 mb-6">
          <h3 className="text-sm font-semibold text-light-gray uppercase tracking-wide">
            Take a Step Back:
          </h3>
          <ul className="space-y-2 text-sm text-light-gray">
            <li className="flex items-start space-x-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Review your bankroll and unit strategy</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Wait for higher confidence opportunities (75%+)</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Consider taking a 1-hour break to reset</span>
            </li>
            <li className="flex items-start space-x-2">
              <span className="text-green-500 mt-0.5">✓</span>
              <span>Focus on quality over quantity</span>
            </li>
          </ul>
        </div>

        {/* Action Button */}
        <button
          onClick={onClose}
          className="w-full bg-electric-blue hover:bg-blue-600 text-white font-semibold py-3 rounded-lg transition-colors"
        >
          I Understand - Continue Responsibly
        </button>

        {/* Footer Note */}
        <p className="text-center text-xs text-light-gray mt-4">
          BeatVegas promotes responsible betting. If you feel you have a gambling problem, 
          please visit <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer" className="text-electric-blue hover:underline">ncpgambling.org</a>
        </p>
      </div>
    </div>
  );
};

export default RiskAlert;
