/**
 * DEV-ONLY Debug Panel for Simulation Data Integrity
 * 
 * Shows all selection metadata to verify mapping integrity:
 * - selection_id consistency across tiles
 * - snapshot_hash consistency
 * - probability mapping correctness
 * - team_id + team_name alignment
 */

import React, { useState } from 'react';

interface SelectionData {
  selection_id?: string;
  team_id?: string;
  team_name?: string;
  line?: number;
  probability?: number;
  market_type?: string;
  market_settlement?: string;
}

interface MarketDebugData {
  event_id: string;
  snapshot_hash?: string;
  server_timestamp?: string;
  home_selection?: SelectionData;
  away_selection?: SelectionData;
  model_preference?: {
    selection_id: string;
    side: string;
    probability: number;
  };
}

interface SimulationDebugPanelProps {
  simulation: any;
  event: any;
}

export const SimulationDebugPanel: React.FC<SimulationDebugPanelProps> = ({ simulation, event }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState<'spread' | 'moneyline' | 'total'>('spread');

  // Extract canonical MarketView data
  const extractMarketData = (marketType: 'spread' | 'moneyline' | 'total'): MarketDebugData => {
    const marketView = simulation?.market_views?.[marketType] || {};
    const selections = marketView.selections || [];
    const homeSelection = selections.find((s: any) => s.side === 'home' || s.side === 'over');
    const awaySelection = selections.find((s: any) => s.side === 'away' || s.side === 'under');
    
    return {
      event_id: marketView.event_id || event?.id || 'UNKNOWN',
      snapshot_hash: marketView.snapshot_hash || 'MISSING',
      server_timestamp: simulation?.created_at || 'MISSING',
      home_selection: {
        selection_id: homeSelection?.selection_id || 'MISSING',
        team_id: event?.home_team_id || 'MISSING',
        team_name: homeSelection?.team_name || event?.home_team || 'MISSING',
        line: homeSelection?.line,
        probability: homeSelection?.model_probability,
        market_type: marketType.toUpperCase(),
        market_settlement: 'PENDING'
      },
      away_selection: {
        selection_id: awaySelection?.selection_id || 'MISSING',
        team_id: event?.away_team_id || 'MISSING',
        team_name: awaySelection?.team_name || event?.away_team || 'MISSING',
        line: awaySelection?.line,
        probability: awaySelection?.model_probability,
        market_type: marketType.toUpperCase(),
        market_settlement: 'PENDING'
      },
      model_preference: {
        selection_id: marketView.model_preference_selection_id || 'MISSING',
        side: marketView.edge_class || 'MISSING',
        probability: 0
      }
    };
  };

  const spreadData = extractMarketData('spread');
  const moneylineData = extractMarketData('moneyline');
  const totalData = extractMarketData('total');

  const currentData = selectedMarket === 'spread' ? spreadData 
    : selectedMarket === 'moneyline' ? moneylineData 
    : totalData;

  // Integrity checks using canonical MarketView
  const checkIntegrity = (data: MarketDebugData): { passed: boolean; issues: string[] } => {
    const marketView = simulation?.market_views?.[selectedMarket];
    const issues: string[] = [];

    if (!marketView) {
      issues.push(`❌ MarketView for ${selectedMarket} is missing`);
      return { passed: false, issues };
    }

    // Check 1: Integrity status from backend
    if (marketView.integrity_status && !marketView.integrity_status.is_valid) {
      marketView.integrity_status.errors?.forEach((err: string) => {
        issues.push(`❌ Backend: ${err}`);
      });
    }

    // Check 2: ui_render_mode
    if (marketView.ui_render_mode === 'SAFE') {
      issues.push('🔒 SAFE MODE ACTIVE — UI rendering blocked');
    }

    // Check 3: snapshot_hash
    if (!data.snapshot_hash || data.snapshot_hash === 'MISSING') {
      issues.push('❌ snapshot_hash is missing');
    }

    // Check 4: selection_ids
    const homeSelectionId = data.home_selection?.selection_id;
    const awaySelectionId = data.away_selection?.selection_id;
    const prefSelectionId = data.model_preference?.selection_id;

    if (homeSelectionId === 'MISSING') issues.push('❌ home_selection_id is missing');
    if (awaySelectionId === 'MISSING') issues.push('❌ away_selection_id is missing');
    if (prefSelectionId === 'MISSING' || prefSelectionId === 'INVALID') {
      if (marketView.edge_class !== 'MARKET_ALIGNED') {
        issues.push('❌ model_preference_selection_id is missing/invalid but edge_class != MARKET_ALIGNED');
      }
    }

    // Check 5: Preference/Direction match
    if (marketView.model_preference_selection_id !== marketView.model_direction_selection_id) {
      issues.push(`❌ CRITICAL: Preference (${marketView.model_preference_selection_id}) != Direction (${marketView.model_direction_selection_id})`);
    }

    // Check 6: Probabilities sum to 1
    const homeProb = data.home_selection?.probability || 0;
    const awayProb = data.away_selection?.probability || 0;
    const probSum = homeProb + awayProb;
    if (Math.abs(probSum - 1.0) > 0.01) {
      issues.push(`⚠️ Probability sum = ${probSum.toFixed(4)}, expected 1.0`);
    }

    return {
      passed: issues.length === 0,
      issues
    };
  };

  const integrity = checkIntegrity(currentData);

  if (!isExpanded) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={() => setIsExpanded(true)}
          className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2"
        >
          <span className="text-lg">🔧</span>
          <span className="font-mono text-sm">DEBUG PANEL</span>
          {!integrity.passed && (
            <span className="bg-red-500 text-white text-xs px-2 py-1 rounded">
              {integrity.issues.length} ISSUES
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-gray-900 border-2 border-purple-500 rounded-lg shadow-2xl w-150 max-h-[80vh] overflow-auto">
      {/* Header */}
      <div className="bg-purple-600 px-4 py-3 flex items-center justify-between sticky top-0">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🔧</span>
          <h3 className="text-white font-bold font-mono">SIMULATION DEBUG PANEL</h3>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-white hover:text-gray-200 text-xl font-bold"
        >
          ✕
        </button>
      </div>

      {/* Market Tabs */}
      <div className="flex gap-2 p-4 border-b border-gray-700">
        {(['spread', 'moneyline', 'total'] as const).map(market => (
          <button
            key={market}
            onClick={() => setSelectedMarket(market)}
            className={`px-4 py-2 rounded font-mono text-sm ${
              selectedMarket === market
                ? 'bg-purple-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {market.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Integrity Status */}
      <div className={`p-4 border-b border-gray-700 ${integrity.passed ? 'bg-green-900/20' : 'bg-red-900/20'}`}>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-2xl">{integrity.passed ? '✅' : '❌'}</span>
          <span className="text-white font-bold">
            {integrity.passed ? 'INTEGRITY CHECK PASSED' : 'INTEGRITY VIOLATIONS DETECTED'}
          </span>
        </div>
        {!integrity.passed && (
          <div className="space-y-1 mt-2">
            {integrity.issues.map((issue, idx) => (
              <div key={idx} className="text-sm text-red-300 font-mono">
                {issue}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Event Info */}
      <div className="p-4 border-b border-gray-700 bg-gray-800/50">
        <h4 className="text-purple-400 font-bold mb-2 font-mono">EVENT METADATA</h4>
        <div className="space-y-1 font-mono text-xs">
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">event_id:</span>
            <span className="text-white">{currentData.event_id}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">snapshot_hash:</span>
            <span className="text-green-400 font-bold">{currentData.snapshot_hash}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">server_timestamp:</span>
            <span className="text-white">{currentData.server_timestamp}</span>
          </div>
        </div>
      </div>

      {/* Home Selection */}
      <div className="p-4 border-b border-gray-700">
        <h4 className="text-blue-400 font-bold mb-2 font-mono">HOME SELECTION</h4>
        <SelectionDebugCard selection={currentData.home_selection!} />
      </div>

      {/* Away Selection */}
      <div className="p-4 border-b border-gray-700">
        <h4 className="text-red-400 font-bold mb-2 font-mono">AWAY SELECTION</h4>
        <SelectionDebugCard selection={currentData.away_selection!} />
      </div>

      {/* Model Preference */}
      <div className="p-4 bg-yellow-900/20">
        <h4 className="text-yellow-400 font-bold mb-2 font-mono">MODEL PREFERENCE</h4>
        <div className="space-y-1 font-mono text-xs">
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">selection_id:</span>
            <span className={`font-bold ${
              currentData.model_preference?.selection_id === currentData.home_selection?.selection_id
                ? 'text-blue-400'
                : currentData.model_preference?.selection_id === currentData.away_selection?.selection_id
                ? 'text-red-400'
                : 'text-red-500'
            }`}>
              {currentData.model_preference?.selection_id}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">side:</span>
            <span className="text-white">{currentData.model_preference?.side}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-400 w-40">probability:</span>
            <span className="text-white">{currentData.model_preference?.probability.toFixed(4)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const SelectionDebugCard: React.FC<{ selection: SelectionData }> = ({ selection }) => (
  <div className="space-y-1 font-mono text-xs bg-gray-800 p-3 rounded">
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">selection_id:</span>
      <span className="text-green-400 font-bold">{selection.selection_id}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">team_id:</span>
      <span className="text-white">{selection.team_id}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">team_name:</span>
      <span className="text-white font-bold">{selection.team_name}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">line:</span>
      <span className="text-white">{selection.line !== null ? selection.line : 'N/A'}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">probability:</span>
      <span className="text-white">{selection.probability?.toFixed(4) || 'N/A'}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">market_type:</span>
      <span className="text-white">{selection.market_type}</span>
    </div>
    <div className="flex gap-2">
      <span className="text-gray-400 w-40">market_settlement:</span>
      <span className="text-white">{selection.market_settlement}</span>
    </div>
  </div>
);

export default SimulationDebugPanel;
