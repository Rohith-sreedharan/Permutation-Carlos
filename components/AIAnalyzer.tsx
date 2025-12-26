import React, { useState } from 'react';
import { Lightbulb, X, AlertTriangle, TrendingUp, Shield, Info } from 'lucide-react';

interface AnalyzerExplanation {
  headline: string;
  what_model_sees: string[];
  key_risks: string[];
  sharp_interpretation: string[];
  bottom_line: {
    state_alignment: 'EDGE' | 'LEAN' | 'NO_PLAY';
    recommended_behavior: string;
    do_not_do: string[];
  };
}

interface AnalyzerResponse {
  success: boolean;
  game_id: string;
  sport: string;
  state: 'EDGE' | 'LEAN' | 'NO_PLAY';
  explanation?: AnalyzerExplanation;
  error?: string;
  fallback_triggered: boolean;
  cached: boolean;
}

interface AIAnalyzerProps {
  gameId: string;
  sport: string;
  marketFocus?: 'SPREAD' | 'TOTAL' | 'ML' | 'PUCKLINE' | 'RUNLINE';
}

export const AIAnalyzer: React.FC<AIAnalyzerProps> = ({
  gameId,
  sport,
  marketFocus
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<AnalyzerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchExplanation = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/analyzer/explain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': localStorage.getItem('userId') || 'anonymous'
        },
        body: JSON.stringify({
          game_id: gameId,
          sport: sport,
          market_focus: marketFocus
        })
      });

      if (!response.ok) {
        throw new Error('Failed to fetch explanation');
      }

      const data: AnalyzerResponse = await response.json();
      setExplanation(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setIsOpen(true);
    if (!explanation) {
      fetchExplanation();
    }
  };

  const handleClose = () => {
    setIsOpen(false);
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case 'EDGE':
        return 'text-green-400 bg-green-900/20 border-green-500';
      case 'LEAN':
        return 'text-yellow-400 bg-yellow-900/20 border-yellow-500';
      case 'NO_PLAY':
        return 'text-gray-400 bg-gray-900/20 border-gray-500';
      default:
        return 'text-gray-400 bg-gray-900/20 border-gray-500';
    }
  };

  return (
    <>
      {/* AI Analyzer Button */}
      <button
        onClick={handleOpen}
        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl"
      >
        <Lightbulb className="w-4 h-4" />
        <span className="text-sm font-medium">AI Analyzer</span>
      </button>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
            
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-700">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-900/30 rounded-lg">
                  <Lightbulb className="w-6 h-6 text-purple-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">AI Analyzer</h2>
                  <p className="text-sm text-gray-400">Model explanation • {sport}</p>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              
              {/* Loading State */}
              {loading && (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
                </div>
              )}

              {/* Error State */}
              {error && (
                <div className="bg-red-900/20 border border-red-500 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-red-400">
                    <AlertTriangle className="w-5 h-5" />
                    <span className="font-medium">Error loading explanation</span>
                  </div>
                  <p className="text-sm text-red-300 mt-2">{error}</p>
                </div>
              )}

              {/* Explanation Content */}
              {!loading && !error && explanation?.explanation && (
                <>
                  {/* State Badge */}
                  <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border ${getStateColor(explanation.state)}`}>
                    <span className="text-sm font-bold">{explanation.state}</span>
                    {explanation.cached && (
                      <span className="text-xs opacity-75">(cached)</span>
                    )}
                  </div>

                  {/* Headline */}
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-2">
                      {explanation.explanation.headline}
                    </h3>
                  </div>

                  {/* What Model Sees */}
                  <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="w-5 h-5 text-blue-400" />
                      <h4 className="font-semibold text-blue-300">What the Model Sees</h4>
                    </div>
                    <ul className="space-y-2">
                      {explanation.explanation.what_model_sees.map((item, idx) => (
                        <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                          <span className="text-blue-400 mt-1">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Key Risks */}
                  <div className="bg-amber-900/20 border border-amber-500/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle className="w-5 h-5 text-amber-400" />
                      <h4 className="font-semibold text-amber-300">Key Risks</h4>
                    </div>
                    <ul className="space-y-2">
                      {explanation.explanation.key_risks.map((item, idx) => (
                        <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                          <span className="text-amber-400 mt-1">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Sharp Interpretation */}
                  <div className="bg-purple-900/20 border border-purple-500/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Shield className="w-5 h-5 text-purple-400" />
                      <h4 className="font-semibold text-purple-300">Sharp Interpretation</h4>
                    </div>
                    <ul className="space-y-2">
                      {explanation.explanation.sharp_interpretation.map((item, idx) => (
                        <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                          <span className="text-purple-400 mt-1">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Bottom Line */}
                  <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Info className="w-5 h-5 text-gray-400" />
                      <h4 className="font-semibold text-white">Bottom Line</h4>
                    </div>
                    
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm text-gray-400 mb-1">Recommended Behavior:</p>
                        <p className="text-sm text-white">
                          {explanation.explanation.bottom_line.recommended_behavior}
                        </p>
                      </div>

                      <div>
                        <p className="text-sm text-gray-400 mb-2">Do NOT:</p>
                        <ul className="space-y-1">
                          {explanation.explanation.bottom_line.do_not_do.map((item, idx) => (
                            <li key={idx} className="text-sm text-red-300 flex items-start gap-2">
                              <span className="text-red-400 mt-1">✗</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>

                  {/* Fallback Warning */}
                  {explanation.fallback_triggered && (
                    <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-yellow-400">
                        <AlertTriangle className="w-4 h-4" />
                        <span className="text-sm font-medium">
                          Limited explanation available. Refer to main EDGE/LEAN/NO_PLAY state.
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Disclaimer */}
              <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
                <p className="text-xs text-gray-400 leading-relaxed">
                  <strong className="text-gray-300">Disclaimer:</strong> This AI explanation is for informational purposes only. 
                  It describes what the model sees based on existing analysis. This is not betting advice. 
                  The EDGE/LEAN/NO_PLAY state remains the authoritative signal. Always do your own research.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AIAnalyzer;
