import React from 'react';
import { AlertTriangle, TrendingUp, Zap } from 'lucide-react';

interface ModelContextCardProps {
  signal_id: string;
  model_context?: {
    prediction?: number;
    volatility_index?: number;
    confidence_score?: number;
    pick_state?: string;
  };
  user_line: string;
  user_confidence: string;
}

/**
 * ModelContextCard
 * Displays BeatVegas model signal data alongside user callout
 * Attached automatically when signal_id is provided
 * Shows: model lean, win probability, volatility badge, confidence band, as_of time
 */
export const ModelContextCard: React.FC<ModelContextCardProps> = ({
  signal_id,
  model_context,
  user_line,
  user_confidence,
}) => {
  if (!model_context) {
    return null;
  }

  const modelPrediction = model_context.prediction || 0.5;
  const volatilityIndex = model_context.volatility_index || 'unknown';
  const modelConfidence = model_context.confidence_score || 0;
  const pickState = model_context.pick_state || 'NEUTRAL';

  // Detect disagreement
  const userIsHighConfidence = user_confidence === 'high';
  const modelIsLow = modelPrediction < 0.45 || modelPrediction > 0.55;
  const hasDisagreement = userIsHighConfidence && modelIsLow;

  // High volatility check
  const isHighVolatility =
    typeof volatilityIndex === 'number' ? volatilityIndex > 0.3 : volatilityIndex?.includes('high');

  return (
    <div className="bg-gradient-to-r from-electric-blue/10 to-purple-500/10 border-l-2 border-electric-blue p-3 rounded-lg space-y-2 my-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-electric-blue rounded-full animate-pulse" />
          <span className="text-xs font-bold text-electric-blue">BEATVEGAS MODEL CONTEXT</span>
        </div>
        <span className="text-xs text-light-gray">as of now</span>
      </div>

      {/* Model Lean + Win Probability */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-charcoal/50 p-2 rounded">
          <p className="text-light-gray">Model Lean</p>
          <p className="font-bold text-white">
            {pickState === 'PICK' && '✓ PICK'}
            {pickState === 'LEAN' && '→ LEAN'}
            {pickState === 'NEUTRAL' && '◇ NEUTRAL'}
            {pickState === 'AVOID' && '⚠ AVOID'}
          </p>
        </div>
        <div className="bg-charcoal/50 p-2 rounded">
          <p className="text-light-gray">Win Probability</p>
          <p className="font-bold text-white">{(modelPrediction * 100).toFixed(1)}%</p>
        </div>
      </div>

      {/* Volatility Badge */}
      {isHighVolatility && (
        <div className="bg-yellow-500/20 border border-yellow-500/30 px-2 py-1 rounded text-xs text-yellow-400 flex items-center space-x-1">
          <Zap size={12} />
          <span>High Variance — wide distribution</span>
        </div>
      )}

      {/* Disagreement Alert */}
      {hasDisagreement && (
        <div className="bg-red-500/20 border border-red-500/30 px-2 py-1 rounded text-xs text-red-400 flex items-center space-x-1">
          <AlertTriangle size={12} />
          <span>Model Disagrees with your confidence level</span>
        </div>
      )}

      {/* Confidence Band */}
      <div className="text-xs">
        <div className="flex justify-between mb-1">
          <span className="text-light-gray">Confidence Band</span>
          <span className="font-bold text-white">
            {modelConfidence > 0.7 ? 'Narrow' : modelConfidence > 0.5 ? 'Medium' : 'Wide'}
          </span>
        </div>
        <div className="w-full bg-navy rounded-full h-1">
          <div
            className={`h-full rounded-full transition ${
              modelConfidence > 0.7
                ? 'bg-green-500'
                : modelConfidence > 0.5
                ? 'bg-yellow-500'
                : 'bg-red-500'
            }`}
            style={{ width: `${modelConfidence * 100}%` }}
          />
        </div>
      </div>

      {/* Simulation Count */}
      <p className="text-xs text-light-gray">
        <strong>Signal ID:</strong> <code className="bg-charcoal/50 px-1 rounded text-electric-blue">{signal_id}</code>
      </p>

      {/* Note */}
      <p className="text-xs text-light-gray italic border-t border-navy/30 pt-2">
        Model context is <strong>statistical output only</strong>. Not a bet recommendation. Your
        edge may differ.
      </p>
    </div>
  );
};

// ============================================================================
// MODERATION PANEL
// ============================================================================

interface ModPanelProps {
  post_id: string;
  user_id: string;
  username: string;
  onActionSubmit: (action: string, reason?: string, duration?: number) => void;
}

export const ModPanel: React.FC<ModPanelProps> = ({ post_id, user_id, username, onActionSubmit }) => {
  const [selectedAction, setSelectedAction] = React.useState<string>('');
  const [reason, setReason] = React.useState('');
  const [duration, setDuration] = React.useState(24);
  const [confirming, setConfirming] = React.useState(false);

  const handleSubmit = (action: string) => {
    setSelectedAction(action);
    setConfirming(true);
  };

  const confirmAction = () => {
    onActionSubmit(selectedAction, reason, duration);
    setReason('');
    setDuration(24);
    setConfirming(false);
    setSelectedAction('');
  };

  const actions = [
    { id: 'delete', label: '🗑️ Delete Post', color: 'red' },
    { id: 'flag', label: '🚩 Flag for Review', color: 'yellow' },
    { id: 'warn', label: '⚠️ Warn User', color: 'orange' },
    { id: 'mute', label: '🔇 Mute (hours)', color: 'purple', hasDuration: true },
    { id: 'lock', label: '🔒 Lock Thread', color: 'blue' },
  ];

  if (confirming) {
    return (
      <div className="bg-navy/50 border border-yellow-500/50 p-3 rounded-lg space-y-3">
        <h4 className="font-bold text-yellow-400">Confirm Moderation Action</h4>
        <p className="text-xs text-light-gray">
          Action: <strong className="text-yellow-400">{selectedAction.toUpperCase()}</strong>
        </p>
        <p className="text-xs text-light-gray">
          Target: <strong className="text-white">{username}</strong>
        </p>

        {selectedAction === 'mute' && (
          <div>
            <label className="text-xs font-bold text-light-gray">Duration (hours)</label>
            <input
              type="number"
              min="1"
              max="168"
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value))}
              className="w-full mt-1 bg-charcoal border border-navy rounded px-2 py-1 text-white text-xs"
            />
          </div>
        )}

        <div>
          <label className="text-xs font-bold text-light-gray">Reason</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Document why this action was taken"
            className="w-full mt-1 bg-charcoal border border-navy rounded px-2 py-1 text-white text-xs"
            rows={2}
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={confirmAction}
            className="flex-1 bg-red-500 text-white font-bold py-1 rounded text-xs hover:bg-red-600 transition"
          >
            Confirm
          </button>
          <button
            onClick={() => {
              setConfirming(false);
              setSelectedAction('');
            }}
            className="flex-1 bg-navy text-light-gray font-bold py-1 rounded text-xs hover:bg-navy/70 transition"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-navy/50 border border-yellow-500/50 p-3 rounded-lg space-y-2">
      <h4 className="font-bold text-yellow-400 text-xs">MODERATION TOOLS</h4>
      <p className="text-xs text-light-gray">Post ID: {post_id}</p>

      <div className="grid grid-cols-2 gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            onClick={() => handleSubmit(action.id)}
            className={`p-2 rounded text-xs font-bold transition text-white ${
              action.color === 'red'
                ? 'bg-red-500/20 hover:bg-red-500/40 border border-red-500/30'
                : action.color === 'yellow'
                ? 'bg-yellow-500/20 hover:bg-yellow-500/40 border border-yellow-500/30'
                : action.color === 'orange'
                ? 'bg-orange-500/20 hover:bg-orange-500/40 border border-orange-500/30'
                : action.color === 'purple'
                ? 'bg-purple-500/20 hover:bg-purple-500/40 border border-purple-500/30'
                : 'bg-blue-500/20 hover:bg-blue-500/40 border border-blue-500/30'
            }`}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
};
