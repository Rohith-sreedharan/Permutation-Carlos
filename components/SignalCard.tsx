import React, { useState } from 'react';
import { Clock, Lock, TrendingUp, TrendingDown, AlertTriangle, Info, ChevronDown, ChevronUp } from 'lucide-react';

interface MarketSnapshot {
  market_snapshot_id: string;
  captured_at: string;
  spread_line?: number;
  total_line?: number;
  ml_home_price?: number;
  ml_away_price?: number;
}

interface GateResult {
  pass_gate: boolean;
  reasons: string[];
  bucket?: string;
}

interface GateEvaluation {
  data_integrity: GateResult;
  sim_power: GateResult;
  model_validity: GateResult;
  volatility: GateResult;
  publish_rcl: GateResult;
}

interface Signal {
  signal_id: string;
  game_id: string;
  sport: string;
  market_key: string;
  selection: string;
  line_value: number;
  odds_price?: number;
  created_at: string;
  intent: string;
  edge_points: number;
  win_prob: number;
  ev?: number;
  volatility_bucket: string;
  confidence_band: string;
  state: 'PICK' | 'LEAN' | 'NO_PLAY';
  gates: GateEvaluation;
  reason_codes: string[];
  explain_summary: string;
  robustness_label?: 'ROBUST' | 'FRAGILE';
  robustness_score?: number;
  model_version: string;
}

interface SignalDelta {
  delta_edge_points: number;
  delta_win_prob: number;
  state_changed: boolean;
  previous_state: string;
  new_state: string;
  gate_changes: string[];
  line_moved: boolean;
  line_move_points?: number;
  change_summary: string;
}

interface LockedSignal {
  locked_at: string;
  lock_reason: string;
  freeze_duration_minutes: number;
}

interface SignalCardProps {
  signal: Signal;
  marketSnapshot?: MarketSnapshot;
  locked?: boolean;
  lockInfo?: LockedSignal;
  hasUpdates?: boolean;
  latestDelta?: SignalDelta;
  onViewHistory?: () => void;
}

const SignalCard: React.FC<SignalCardProps> = ({
  signal,
  marketSnapshot,
  locked = false,
  lockInfo,
  hasUpdates = false,
  latestDelta,
  onViewHistory
}) => {
  const [showDetails, setShowDetails] = useState(false);
  const [showDelta, setShowDelta] = useState(false);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      timeZone: 'America/New_York'
    });
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'America/New_York'
    });
  };

  const stateColors = {
    PICK: 'bg-green-500/20 border-green-500 text-green-400',
    LEAN: 'bg-blue-500/20 border-blue-500 text-blue-400',
    NO_PLAY: 'bg-red-500/20 border-red-500 text-red-400'
  };

  const volatilityColors = {
    LOW: 'text-green-400',
    MEDIUM: 'text-yellow-400',
    HIGH: 'text-red-400'
  };

  const robustnessColors = {
    ROBUST: 'text-green-400 bg-green-500/10',
    FRAGILE: 'text-orange-400 bg-orange-500/10'
  };

  return (
    <div className={`rounded-lg border-2 p-4 transition-all ${stateColors[signal.state]}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-lg">{signal.selection}</span>
            {locked && (
              <Lock className="w-4 h-4 text-yellow-400" aria-label="Signal Locked" />
            )}
            {signal.robustness_label && (
              <span className={`px-2 py-0.5 rounded text-xs font-semibold ${robustnessColors[signal.robustness_label]}`}>
                {signal.robustness_label}
              </span>
            )}
          </div>
          <div className="text-sm opacity-80">
            {signal.market_key} • {signal.sport}
          </div>
        </div>
        <div className="text-right">
          <div className={`font-bold text-xl ${stateColors[signal.state]}`}>
            {signal.state}
          </div>
          <div className="text-xs opacity-60">
            {signal.volatility_bucket} Vol
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="bg-black/20 rounded p-2">
          <div className="text-xs opacity-60">Edge</div>
          <div className="font-bold">
            {signal.edge_points > 0 ? '+' : ''}{signal.edge_points.toFixed(1)}
          </div>
        </div>
        <div className="bg-black/20 rounded p-2">
          <div className="text-xs opacity-60">Win %</div>
          <div className="font-bold">{(signal.win_prob * 100).toFixed(1)}%</div>
        </div>
        {signal.ev !== undefined && (
          <div className="bg-black/20 rounded p-2">
            <div className="text-xs opacity-60">EV</div>
            <div className="font-bold">{signal.ev > 0 ? '+' : ''}{signal.ev.toFixed(2)}%</div>
          </div>
        )}
      </div>

      {/* Snapshot Info */}
      <div className="flex items-center gap-3 text-xs opacity-70 mb-3 flex-wrap">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>As of: {formatTime(signal.created_at)} ET</span>
        </div>
        {marketSnapshot && (
          <div>
            Line: {signal.line_value} {signal.odds_price && `(${signal.odds_price})`}
          </div>
        )}
        <div>Model v{signal.model_version}</div>
        <div className="uppercase text-[10px] px-1.5 py-0.5 bg-gray-700 rounded">
          {signal.intent.replace('_', ' ')}
        </div>
      </div>

      {/* Explanation */}
      <div className="bg-black/30 rounded p-2 mb-3 text-sm">
        {signal.explain_summary}
      </div>

      {/* Update Notification */}
      {hasUpdates && latestDelta && (
        <div className="bg-yellow-500/20 border border-yellow-500 rounded p-3 mb-3">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                <span className="font-semibold text-yellow-400">Update Available</span>
              </div>
              <div className="text-sm">{latestDelta.change_summary}</div>
              {latestDelta.state_changed && (
                <div className="text-xs mt-1 opacity-80">
                  {latestDelta.previous_state} → {latestDelta.new_state}
                </div>
              )}
            </div>
            <button
              onClick={() => setShowDelta(!showDelta)}
              className="text-yellow-400 hover:text-yellow-300"
            >
              {showDelta ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          </div>

          {/* Delta Details */}
          {showDelta && (
            <div className="mt-3 pt-3 border-t border-yellow-500/30 space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <div className="text-xs opacity-60">Δ Edge</div>
                  <div className={latestDelta.delta_edge_points > 0 ? 'text-green-400' : 'text-red-400'}>
                    {latestDelta.delta_edge_points > 0 ? '+' : ''}{latestDelta.delta_edge_points.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-xs opacity-60">Δ Win %</div>
                  <div className={latestDelta.delta_win_prob > 0 ? 'text-green-400' : 'text-red-400'}>
                    {latestDelta.delta_win_prob > 0 ? '+' : ''}{(latestDelta.delta_win_prob * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
              {latestDelta.line_moved && latestDelta.line_move_points && (
                <div className="text-xs">
                  Line moved: {latestDelta.line_move_points > 0 ? '+' : ''}{latestDelta.line_move_points} points
                </div>
              )}
              {latestDelta.gate_changes.length > 0 && (
                <div className="text-xs">
                  Gates changed: {latestDelta.gate_changes.join(', ')}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Lock Info */}
      {locked && lockInfo && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded p-2 mb-3 text-xs">
          <div className="flex items-center gap-2">
            <Lock className="w-3 h-3 text-yellow-400" />
            <span>
              Signal locked at {formatTime(lockInfo.locked_at)} • 
              Freeze: {lockInfo.freeze_duration_minutes}m • 
              {lockInfo.lock_reason}
            </span>
          </div>
        </div>
      )}

      {/* Expandable Details */}
      <button
        onClick={() => setShowDetails(!showDetails)}
        className="w-full flex items-center justify-between text-sm opacity-70 hover:opacity-100 transition-opacity"
      >
        <span>Signal Details</span>
        {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {showDetails && (
        <div className="mt-3 pt-3 border-t border-gray-700 space-y-2 text-sm">
          {/* Gate Status */}
          <div>
            <div className="text-xs font-semibold mb-1 opacity-60">Gate Status</div>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <div className={signal.gates.data_integrity.pass_gate ? 'text-green-400' : 'text-red-400'}>
                ✓ Data Integrity
              </div>
              <div className={signal.gates.sim_power.pass_gate ? 'text-green-400' : 'text-red-400'}>
                ✓ Sim Power
              </div>
              <div className={signal.gates.model_validity.pass_gate ? 'text-green-400' : 'text-red-400'}>
                ✓ Model Valid
              </div>
              <div className={signal.gates.volatility.pass_gate ? 'text-green-400' : 'text-red-400'}>
                ✓ Volatility
              </div>
              <div className={signal.gates.publish_rcl.pass_gate ? 'text-green-400' : 'text-red-400'}>
                ✓ Publish RCL
              </div>
            </div>
          </div>

          {/* Reason Codes */}
          {signal.reason_codes.length > 0 && (
            <div>
              <div className="text-xs font-semibold mb-1 opacity-60">Failure Reasons</div>
              <div className="flex flex-wrap gap-1">
                {signal.reason_codes.map((code, idx) => (
                  <span key={idx} className="px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded text-[10px]">
                    {code.replace('_', ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Robustness */}
          {signal.robustness_score !== undefined && (
            <div>
              <div className="text-xs font-semibold mb-1 opacity-60">Robustness Score</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-full rounded-full ${signal.robustness_score >= 70 ? 'bg-green-500' : 'bg-orange-500'}`}
                    style={{ width: `${signal.robustness_score}%` }}
                  />
                </div>
                <span className="text-xs">{signal.robustness_score}/100</span>
              </div>
            </div>
          )}

          {/* Signal ID */}
          <div className="text-xs opacity-40 font-mono">
            ID: {signal.signal_id}
          </div>

          {/* View History Button */}
          {onViewHistory && (
            <button
              onClick={onViewHistory}
              className="w-full mt-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
            >
              View Signal History
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default SignalCard;
