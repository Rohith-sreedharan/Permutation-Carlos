/**
 * GameDetail Component - Canonical MarketDecision Architecture
 * 
 * ARCHITECTURAL REQUIREMENTS (NON-NEGOTIABLE):
 * ============================================
 * 1. ZERO client-side decision computation
 * 2. ONE MarketDecision object per market from backend
 * 3. ALL UI surfaces render from the same object
 * 4. NO UI inference of pick/direction/status/reasons
 * 5. Backend computes EVERYTHING, UI displays VERBATIM
 * 
 * FORBIDDEN (will cause contradictions):
 * - getSelection, getPreferredSelection helpers
 * - validateMarketView, validateEdge
 * - calculateCLV, explainEdgeSource
 * - Any Math.abs on spread values
 * - Any UI logic that derives team/sign/edge from probabilities
 * 
 * STALE RESPONSE PREVENTION:
 * - requestIdRef tracks fetch ordering
 * - decision_version comparison rejects older responses
 * 
 * If classification = MARKET_ALIGNED:
 *   → NO edge language anywhere
 *   → Model Direction HIDDEN
 *   → "Why This Edge Exists" shows "No valid edge detected"
 */

import React, { useState, useEffect, useRef } from 'react';
import { MarketDecision, GameDecisions, MarketType, Classification } from '../types/MarketDecision';
import { fetchEventsFromDB } from '../services/api';
import LoadingSpinner from './LoadingSpinner';
import type { Event } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface GameDetailProps {
  gameId: string;
  onBack: () => void;
}

const GameDetail: React.FC<GameDetailProps> = ({ gameId, onBack }) => {
  const [decisions, setDecisions] = useState<GameDecisions | null>(null);
  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMarketTab, setActiveMarketTab] = useState<MarketType>('spread');
  const requestIdRef = useRef(0);  // Track request ordering for stale prevention
  
  useEffect(() => {
    loadGameDecisions();
  }, [gameId]);

  const loadGameDecisions = async () => {
    if (!gameId) return;

    // Increment request ID to track this specific fetch
    const currentRequestId = ++requestIdRef.current;

    try {
      setLoading(true);
      setError(null);

      // First fetch event to get sport_key (league)
      const eventsData = await fetchEventsFromDB(undefined, undefined, false, 500);
      const eventData = eventsData.find((e: Event) => e.id === gameId);
      
      if (!eventData) {
        throw new Error('Game not found');
      }

      setEvent(eventData);

      // Map sport_key to league (basketball_nba → NBA, etc)
      const leagueMap: Record<string, string> = {
        'basketball_nba': 'NBA',
        'americanfootball_nfl': 'NFL',
        'americanfootball_ncaaf': 'NCAAF',
        'icehockey_nhl': 'NHL',
        'baseball_mlb': 'MLB',
        'basketball_ncaab': 'NCAAB'
      };
      const league = leagueMap[eventData.sport_key] || 'NBA';

      // Fetch from SINGLE unified endpoint with league parameter
      const token = localStorage.getItem('authToken');
      const decisionsData = await fetch(`${API_BASE_URL}/api/games/${league}/${gameId}/decisions`, {
        headers: { 'Authorization': token ? `Bearer ${token}` : '' }
      }).then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        return res.json();
      });

      // STALE RESPONSE REJECTION: Ignore if newer request already completed
      if (currentRequestId !== requestIdRef.current) {
        console.warn('[STALE REJECTED] Outdated response ignored:', {
          requestId: currentRequestId,
          currentRequestId: requestIdRef.current,
          game_id: gameId
        });
        return;
      }

      // ATOMIC VERSION CHECK: Reject if older than current data
      if (decisions && decisionsData.decision_version <= decisions.decision_version) {
        console.warn('[STALE REJECTED] Older decision_version:', {
          incoming: decisionsData.decision_version,
          current: decisions.decision_version,
          computed_at_incoming: decisionsData.computed_at,
          computed_at_current: decisions.computed_at
        });
        return;
      }

      setDecisions(decisionsData);
    } catch (err: any) {
      console.error('Failed to load game decisions:', err);
      setError(err.message || 'Failed to load game data');
    } finally {
      setLoading(false);
    }
  };

  // PRESENTATION-ONLY HELPERS (no logic, just formatting)
  const formatLine = (line: number | undefined): string => {
    if (line === undefined) return 'N/A';
    return line > 0 ? `+${line}` : `${line}`;
  };

  const formatOdds = (odds: number | undefined): string => {
    if (odds === undefined) return 'N/A';
    return odds > 0 ? `+${odds}` : `${odds}`;
  };

  const getClassificationBadge = (classification: Classification): { text: string; color: string } => {
    switch (classification) {
      case 'EDGE': return { text: 'EDGE DETECTED', color: 'text-neon-green bg-neon-green/20 border-neon-green' };
      case 'LEAN': return { text: 'LEAN', color: 'text-yellow-500 bg-yellow-500/20 border-yellow-500' };
      case 'MARKET_ALIGNED': return { text: 'MARKET ALIGNED — NO EDGE', color: 'text-light-gray bg-gray-800/20 border-gray-600' };
      case 'NO_ACTION': return { text: 'NO ACTION', color: 'text-bold-red bg-red-900/20 border-bold-red' };
    }
  };

  const renderMarketTab = (decision: MarketDecision | null, marketType: MarketType) => {
    if (!decision) {
      return (
        <div className="p-6 bg-navy/50 rounded-xl border border-light-gray/20 text-center text-light-gray">
          {marketType.toUpperCase()} market data unavailable
        </div>
      );
    }

    // Integrity block check
    if (decision.release_status === 'BLOCKED_BY_INTEGRITY') {
      return (
        <div className="p-6 bg-red-900/20 border-2 border-red-500 rounded-lg">
          <div className="text-red-400 font-bold text-lg mb-2">🚫 INTEGRITY BLOCKED</div>
          <div className="text-red-300 text-sm mb-3">
            This market analysis was blocked due to data integrity violations.
          </div>
          {decision.validator_failures && decision.validator_failures.length > 0 && (
            <div className="text-xs text-red-300/70 space-y-1">
              {decision.validator_failures.map((failure, idx) => (
                <div key={idx}>• {failure}</div>
              ))}
            </div>
          )}
        </div>
      );
    }

    const badge = getClassificationBadge(decision.classification);

    return (
      <div className="space-y-6">
        {/* Classification Badge */}
        <div className={`inline-block px-4 py-2 rounded-lg border-2 font-bold ${badge.color}`}>
          {badge.text}
        </div>

        {/* Market Status */}
        <div className="bg-navy/50 rounded-xl p-6 border border-light-gray/20">
          <h3 className="text-lg font-bold text-white mb-4">Market Status</h3>
          <div className="text-light-gray">
            {decision.classification === 'MARKET_ALIGNED' 
              ? 'Market and model consensus detected. No directional preference.'
              : decision.release_status === 'OFFICIAL'
                ? `Official ${decision.classification} - eligible for release`
                : `Info-only ${decision.classification}`
            }
          </div>
        </div>

        {/* Model Preference/Direction - ONLY if not MARKET_ALIGNED */}
        {decision.classification !== 'MARKET_ALIGNED' && decision.classification !== 'NO_ACTION' && (
          <div className="bg-electric-blue/10 rounded-xl p-6 border border-electric-blue/30">
            <h3 className="text-lg font-bold text-electric-blue mb-4">Model Preference</h3>
            {marketType === 'spread' || marketType === 'moneyline' ? (
              <div className="space-y-2">
                <div className="text-white text-xl font-bold">{decision.pick.team_name}</div>
                {decision.market.line !== undefined && (
                  <div className="text-light-gray">
                    Market Line: {formatLine(decision.market.line)}
                  </div>
                )}
                {decision.model.fair_line !== undefined && (
                  <div className="text-light-gray">
                    Model Fair Line: {formatLine(decision.model.fair_line)}
                  </div>
                )}
                {decision.edge.edge_points !== undefined && (
                  <div className="text-neon-green text-lg font-bold">
                    Edge: {decision.edge.edge_points.toFixed(1)} points
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-white text-xl font-bold">{decision.pick.total_side}</div>
                {decision.market.line !== undefined && (
                  <div className="text-light-gray">
                    Market Total: {decision.market.line}
                  </div>
                )}
                {decision.model.fair_total !== undefined && (
                  <div className="text-light-gray">
                    Model Fair Total: {decision.model.fair_total.toFixed(1)}
                  </div>
                )}
                {decision.edge.edge_points !== undefined && (
                  <div className="text-neon-green text-lg font-bold">
                    Edge: {decision.edge.edge_points.toFixed(1)} points
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Cover Probability */}
        <div className="bg-navy/50 rounded-xl p-6 border border-light-gray/20">
          <h3 className="text-lg font-bold text-white mb-4">Cover Probability</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-light-gray text-sm mb-1">Model Probability</div>
              <div className="text-white text-2xl font-bold">
                {(decision.probabilities.model_prob * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-light-gray text-sm mb-1">Market Implied</div>
              <div className="text-white text-2xl font-bold">
                {(decision.probabilities.market_implied_prob * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>

        {/* Why This Edge Exists */}
        <div className="bg-navy/50 rounded-xl p-6 border border-light-gray/20">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <span>💡</span>
            Why This Edge Exists
          </h3>
          {decision.reasons && decision.reasons.length > 0 ? (
            <ul className="space-y-2">
              {decision.reasons.map((reason, idx) => (
                <li key={idx} className="text-light-gray flex items-start gap-2">
                  <span className="text-neon-green">•</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-light-gray">
              {decision.classification === 'MARKET_ALIGNED' 
                ? 'No valid edge detected. Market appears efficiently priced.'
                : 'Edge reasoning unavailable.'
              }
            </div>
          )}
        </div>

        {/* Debug Info (dev only) */}
        {process.env.NODE_ENV === 'development' && (
          <div className="bg-gray-900/50 rounded-xl p-4 border border-gray-700 text-xs font-mono">
            <div className="text-gray-400 mb-2">Debug Info</div>
            <div className="text-gray-500 space-y-1">
              <div>inputs_hash: {decision.debug.inputs_hash}</div>
              <div>selection_id: {decision.selection_id}</div>
              {decision.debug.trace_id && <div>trace_id: {decision.debug.trace_id}</div>}
              {decision.debug.decision_version && <div>version: {decision.debug.decision_version}</div>}
              {decision.debug.computed_at && <div>computed: {decision.debug.computed_at}</div>}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderUnifiedSummary = () => {
    if (!decisions) return null;

    // Deterministic selector: prioritize OFFICIAL EDGE, then LEAN, then MARKET_ALIGNED
    let primaryDecision: MarketDecision | null = null;
    let primaryMarket: MarketType | null = null;

    // Priority 1: OFFICIAL + EDGE
    for (const [market, decision] of Object.entries({ 
      spread: decisions.spread, 
      moneyline: decisions.moneyline, 
      total: decisions.total 
    })) {
      if (decision && decision.release_status === 'OFFICIAL' && decision.classification === 'EDGE') {
        primaryDecision = decision;
        primaryMarket = market as MarketType;
        break;
      }
    }

    // Priority 2: LEAN
    if (!primaryDecision) {
      for (const [market, decision] of Object.entries({ 
        spread: decisions.spread, 
        moneyline: decisions.moneyline, 
        total: decisions.total 
      })) {
        if (decision && decision.classification === 'LEAN') {
          primaryDecision = decision;
          primaryMarket = market as MarketType;
          break;
        }
      }
    }

    // Priority 3: Show best available (even if MARKET_ALIGNED)
    if (!primaryDecision) {
      primaryDecision = decisions.spread || decisions.moneyline || decisions.total;
      primaryMarket = decisions.spread ? 'spread' : decisions.moneyline ? 'moneyline' : 'total';
    }

    if (!primaryDecision || !primaryMarket) {
      return (
        <div className="bg-navy/50 rounded-xl p-6 border border-light-gray/20 text-center text-light-gray">
          No market decisions available
        </div>
      );
    }

    const badge = getClassificationBadge(primaryDecision.classification);

    return (
      <div className="bg-linear-to-br from-navy/80 to-navy/40 rounded-xl p-8 border-2 border-electric-blue/50">
        <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
          <span>📊</span>
          Final Unified Summary
        </h2>

        <div className="space-y-4">
          {/* Classification */}
          <div className={`inline-block px-4 py-2 rounded-lg border-2 font-bold ${badge.color}`}>
            {badge.text}
          </div>

          {/* Market Type */}
          <div className="text-light-gray text-sm">
            {primaryMarket.toUpperCase()} MARKET
          </div>

          {/* Pick Display - ONLY if not MARKET_ALIGNED */}
          {primaryDecision.classification !== 'MARKET_ALIGNED' && primaryDecision.classification !== 'NO_ACTION' && (
            <div className="bg-electric-blue/10 rounded-lg p-6 border border-electric-blue/30">
              <div className="text-white text-2xl font-bold mb-2">
                {primaryMarket === 'total' 
                  ? `${primaryDecision.pick.total_side} ${primaryDecision.market.line || ''}`
                  : `${primaryDecision.pick.team_name} ${primaryDecision.market.line ? formatLine(primaryDecision.market.line) : ''}`
                }
              </div>
              <div className="text-light-gray text-sm">
                {primaryDecision.classification} • {primaryDecision.release_status}
              </div>
              {primaryDecision.edge.edge_points !== undefined && (
                <div className="text-neon-green text-lg font-bold mt-2">
                  +{primaryDecision.edge.edge_points.toFixed(1)} pt edge
                </div>
              )}
            </div>
          )}

          {/* Reasons (uses SAME reasons from decision object) */}
          {primaryDecision.reasons && primaryDecision.reasons.length > 0 && (
            <div className="space-y-2 mt-4">
              {primaryDecision.reasons.map((reason, idx) => (
                <div key={idx} className="flex items-start gap-2 text-light-gray">
                  <span className="text-neon-green">✓</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          )}

          {/* MARKET_ALIGNED state */}
          {primaryDecision.classification === 'MARKET_ALIGNED' && (
            <div className="text-light-gray">
              Model and market consensus detected. No directional preference.
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button onClick={onBack} className="text-gold hover:text-white mb-4 flex items-center space-x-2">
          <span>←</span> <span>Back</span>
        </button>
        <div className="flex items-center justify-center h-96">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button onClick={onBack} className="text-gold hover:text-white mb-4 flex items-center space-x-2">
          <span>←</span> <span>Back</span>
        </button>
        <div className="text-center space-y-4">
          <div className="text-bold-red text-xl">{error}</div>
          <button
            onClick={() => loadGameDecisions()}
            className="bg-electric-blue text-white px-6 py-2 rounded-lg hover:opacity-80"
          >
            🔄 Retry
          </button>
        </div>
      </div>
    );
  }

  if (!decisions || !event) {
    return (
      <div className="min-h-screen bg-[#0a0e1a] p-6">
        <button onClick={onBack} className="text-gold hover:text-white mb-4 flex items-center space-x-2">
          <span>←</span> <span>Back</span>
        </button>
        <div className="text-center text-white p-8">Game data unavailable</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      {/* Back Navigation */}
      <button onClick={onBack} className="text-gold hover:text-white mb-4 flex items-center space-x-2">
        <span>←</span> <span>Back to Dashboard</span>
      </button>

      {/* Game Header */}
      <div className="bg-navy/50 rounded-xl p-8 border border-light-gray/20 mb-6">
        <div className="text-center">
          <div className="text-light-gray text-sm mb-2">{event.sport_key?.toUpperCase() || 'NBA'}</div>
          <h1 className="text-3xl font-bold text-white mb-4">
            {event.away_team} @ {event.home_team}
          </h1>
          <div className="text-light-gray text-sm">
            {new Date(event.local_date_est || event.commence_time).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Unified Summary (renders from canonical decision) */}
      {renderUnifiedSummary()}

      {/* Market Tabs */}
      <div className="mt-8">
        <div className="flex gap-2 mb-6">
          {['spread', 'moneyline', 'total'].map((market) => (
            <button
              key={market}
              onClick={() => setActiveMarketTab(market as MarketType)}
              className={`px-6 py-3 rounded-lg font-bold transition ${
                activeMarketTab === market
                  ? 'bg-electric-blue text-white'
                  : 'bg-navy/50 text-light-gray hover:bg-navy/70'
              }`}
            >
              {market.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Active Market View (renders from canonical decision) */}
        {activeMarketTab === 'spread' && renderMarketTab(decisions.spread, 'spread')}
        {activeMarketTab === 'moneyline' && renderMarketTab(decisions.moneyline, 'moneyline')}
        {activeMarketTab === 'total' && renderMarketTab(decisions.total, 'total')}
      </div>

      {/* Integrity Check Display */}
      {decisions.meta && (
        <div className="mt-8 bg-gray-900/50 rounded-xl p-4 border border-gray-700">
          <div className="text-gray-400 text-sm mb-2">Data Integrity</div>
          <div className="text-gray-500 text-xs font-mono space-y-1">
            <div>inputs_hash: {decisions.meta.inputs_hash}</div>
            <div>computed_at: {decisions.meta.computed_at}</div>
            <div>
              All markets keyed to same hash: {
                decisions.spread?.debug.inputs_hash === decisions.meta.inputs_hash &&
                decisions.moneyline?.debug.inputs_hash === decisions.meta.inputs_hash &&
                decisions.total?.debug.inputs_hash === decisions.meta.inputs_hash
                  ? '✓ PASS' : '✗ FAIL'
              }
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GameDetail;
